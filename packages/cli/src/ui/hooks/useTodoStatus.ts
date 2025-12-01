/**
 * Todo Status Hook
 * Listens for todo_update events from WebSocket and manages current todo state.
 */

import { useState, useEffect } from 'react';
import type { ConnectionManager } from '@toyoura-nagisa/core';

export interface TodoItem {
  todo_id: string;
  content: string;
  activeForm: string;
  status: 'pending' | 'in_progress' | 'completed';
  session_id: string;
  created_at: number;
  updated_at: number;
  metadata?: Record<string, any>;
}

interface TodoUpdateEvent {
  todo: TodoItem | null;
}

export interface UseTodoStatusOptions {
  connectionManager: ConnectionManager;
}

export interface UseTodoStatusReturn {
  currentTodo: TodoItem | null;
  isActive: boolean;
}

/**
 * Hook for tracking current in-progress todo status.
 */
export function useTodoStatus({
  connectionManager,
}: UseTodoStatusOptions): UseTodoStatusReturn {
  const [currentTodo, setCurrentTodo] = useState<TodoItem | null>(null);

  useEffect(() => {
    const handleTodoUpdate = (event: TodoUpdateEvent) => {
      setCurrentTodo(event.todo);
    };

    connectionManager.on('todo_update', handleTodoUpdate);

    return () => {
      connectionManager.off('todo_update', handleTodoUpdate);
    };
  }, [connectionManager]);

  return {
    currentTodo,
    isActive: currentTodo !== null && currentTodo.status === 'in_progress',
  };
}
