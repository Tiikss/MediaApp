import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

const API_BASE = 'http://localhost:8000';

export interface StatusResponse {
  status: 'not_started' | 'processing' | 'completed' | 'error';
}

export interface UploadResponse {
  message: string;
  count: number;
}

export type SseEvent =
  | { type: 'status'; content: 'thinking' | 'searching' | 'responding' }
  | { type: 'token'; content: string }
  | { type: 'done' }
  | { type: 'error'; content: string };

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  getStatus(): Observable<StatusResponse> {
    return this.http.get<StatusResponse>(`${API_BASE}/api/status`);
  }

  uploadFiles(files: File[]): Observable<UploadResponse> {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f, f.name));
    return this.http.post<UploadResponse>(`${API_BASE}/api/upload`, formData);
  }

  async *chatStream(message: string, threadId = 'document_chat'): AsyncGenerator<SseEvent> {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, thread_id: threadId }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Nepoznata greška' }));
      throw new Error(err.detail ?? 'Greška pri slanju poruke.');
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event: SseEvent = JSON.parse(line.slice(6));
            yield event;
          } catch {
            // ignore malformed lines
          }
        }
      }
    }
  }
}
