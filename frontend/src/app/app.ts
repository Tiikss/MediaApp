import {
  Component,
  signal,
  inject,
  ElementRef,
  ViewChild,
  AfterViewChecked,
  OnInit,
  ChangeDetectorRef,
  SecurityContext,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer } from '@angular/platform-browser';
import { marked } from 'marked';
import { ApiService } from './api.service';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  status?: 'thinking' | 'searching' | 'responding' | null;
  streaming?: boolean;
}

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit, AfterViewChecked {
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef<HTMLDivElement>;
  @ViewChild('fileInput') private fileInput!: ElementRef<HTMLInputElement>;

  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  private sanitizer = inject(DomSanitizer);

  messages = signal<ChatMessage[]>([]);
  processingStatus = signal<'not_started' | 'processing' | 'completed' | 'error'>('not_started');
  selectedFiles = signal<File[]>([]);
  isSendingChat = signal(false);
  isUploadingFiles = signal(false);
  userInput = signal('');
  sidebarOpen = signal(true);

  private shouldScrollToBottom = false;

  ngOnInit(): void {
    this.api.getStatus().subscribe({
      next: (res) => this.processingStatus.set(res.status),
      error: () => {},
    });
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom(true);
      this.shouldScrollToBottom = false;
    }
  }

  private scrollToBottom(smooth = false): void {
    requestAnimationFrame(() => {
      try {
        const el = this.messagesContainer?.nativeElement;
        if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'instant' });
      } catch {}
    });
  }

  onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      this.selectedFiles.set(Array.from(input.files));
    }
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    const files = event.dataTransfer?.files;
    if (files) {
      const allowed = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'];
      const filtered = Array.from(files).filter(f => allowed.includes(f.type) || f.name.endsWith('.txt') || f.name.endsWith('.pdf') || f.name.endsWith('.docx'));
      this.selectedFiles.set(filtered);
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
  }

  processFiles(): void {
    const files = this.selectedFiles();
    if (!files.length) return;

    this.isUploadingFiles.set(true);
    this.processingStatus.set('processing');

    this.api.uploadFiles(files).subscribe({
      next: () => {
        this.processingStatus.set('completed');
        this.isUploadingFiles.set(false);
        this.selectedFiles.set([]);
        if (this.fileInput?.nativeElement) {
          this.fileInput.nativeElement.value = '';
        }
      },
      error: (err) => {
        this.processingStatus.set('error');
        this.isUploadingFiles.set(false);
        console.error('Upload error:', err);
      },
    });
  }

  async sendMessage(): Promise<void> {
    const text = this.userInput().trim();
    if (!text || this.isSendingChat()) return;

    this.messages.update(msgs => [...msgs, { role: 'user', content: text }]);
    this.userInput.set('');
    this.isSendingChat.set(true);
    this.shouldScrollToBottom = true;

    const assistantIndex = this.messages().length;
    this.messages.update(msgs => [
      ...msgs,
      { role: 'assistant', content: '', status: 'thinking', streaming: true },
    ]);
    this.shouldScrollToBottom = true;

    const charQueue: string[] = [];
    let displayedRaw = '';
    let streamDone = false;

    const typingInterval = setInterval(() => {
      const CHARS_PER_TICK = 3; 
      let dequeued = 0;
      for (let i = 0; i < CHARS_PER_TICK && charQueue.length > 0; i++) {
        displayedRaw += charQueue.shift()!;
        dequeued++;
      }
      if (dequeued === 0) {
        if (streamDone) {
          clearInterval(typingInterval);
          this.messages.update(msgs => {
            const updated = [...msgs];
            updated[assistantIndex] = { ...updated[assistantIndex], streaming: false };
            return updated;
          });
          this.cdr.detectChanges();
          this.scrollToBottom();
        }
        return;
      }

      const html = this.renderMarkdown(displayedRaw);
      this.messages.update(msgs => {
        const updated = [...msgs];
        updated[assistantIndex] = { ...updated[assistantIndex], content: html, status: null };
        return updated;
      });
      this.cdr.detectChanges();
      this.scrollToBottom();

      if (streamDone && charQueue.length === 0) {
        clearInterval(typingInterval);
        this.messages.update(msgs => {
          const updated = [...msgs];
          updated[assistantIndex] = { ...updated[assistantIndex], streaming: false };
          return updated;
        });
        this.cdr.detectChanges();
        this.scrollToBottom();
      }
    }, 30); 

    try {
      const stream = this.api.chatStream(text);

      for await (const event of stream) {
        if (event.type === 'status') {
          this.messages.update(msgs => {
            const updated = [...msgs];
            updated[assistantIndex] = { ...updated[assistantIndex], status: event.content as any };
            return updated;
          });
        } else if (event.type === 'token') {
          charQueue.push(...event.content.split(''));
        } else if (event.type === 'done') {
          streamDone = true;
        } else if (event.type === 'error') {
          clearInterval(typingInterval);
          const errHtml = `<span class="error-text">❌ Greška: ${event.content}</span>`;
          this.messages.update(msgs => {
            const updated = [...msgs];
            updated[assistantIndex] = { ...updated[assistantIndex], content: errHtml, streaming: false, status: null };
            return updated;
          });
          this.isSendingChat.set(false);
          this.cdr.detectChanges();
          return;
        }
      }
      streamDone = true;
      this.isSendingChat.set(false);
      this.cdr.detectChanges();
    } catch (err: any) {
      clearInterval(typingInterval);
      const errHtml = `<span class="error-text">❌ Greška: ${err?.message ?? 'Nepoznata greška'}</span>`;
      this.messages.update(msgs => {
        const updated = [...msgs];
        updated[assistantIndex] = { ...updated[assistantIndex], content: errHtml, streaming: false, status: null };
        return updated;
      });
      this.isSendingChat.set(false);
      this.shouldScrollToBottom = true;
      this.cdr.detectChanges();
    }
  }

  onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  private renderMarkdown(raw: string): string {
    const html = marked.parse(raw, { async: false }) as string;
    return this.sanitizer.sanitize(SecurityContext.HTML, html) ?? '';
  }

get statusLabel(): string {
    switch (this.processingStatus()) {
      case 'not_started': return '⏳ Nema fajlova u bazi. Dodajte fajlove.';
      case 'processing':  return '⚙️ Fajlovi se obrađuju...';
      case 'completed':   return '✅ Fajlovi su uspješno obrađeni!';
      case 'error':       return '❌ Greška pri obradi. Pokušajte ponovo.';
    }
  }
}
