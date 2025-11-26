/**
 * Text Buffer with useReducer pattern
 * Reference: Gemini CLI ui/components/shared/text-buffer.ts (simplified)
 *
 * Uses useReducer to ensure all state updates are synchronous,
 * preventing issues with IME rapid character input.
 */

import { useReducer, useCallback, useMemo, useEffect } from 'react';
import { toCodePoints, cpLen, cpSlice, stripUnsafeCharacters } from './textUtils.js';
import type { Key } from '../contexts/KeypressContext.js';

// Direction types for cursor movement
export type Direction = 'left' | 'right' | 'up' | 'down' | 'home' | 'end';

// ─────────────────────────────────────────────────────────────────────────────
// State & Action Types
// ─────────────────────────────────────────────────────────────────────────────

export interface TextBufferState {
  lines: string[];
  cursorRow: number;
  cursorCol: number;
}

export type TextBufferAction =
  | { type: 'set_text'; payload: string }
  | { type: 'insert'; payload: string }
  | { type: 'backspace' }
  | { type: 'delete' }
  | { type: 'move'; payload: { dir: Direction } }
  | { type: 'newline' }
  | { type: 'delete_word_left' }
  | { type: 'kill_line_left' }
  | { type: 'kill_line_right' }
  | { type: 'set_cursor_absolute'; payload: number };

// ─────────────────────────────────────────────────────────────────────────────
// Reducer Logic
// ─────────────────────────────────────────────────────────────────────────────

function textBufferReducer(
  state: TextBufferState,
  action: TextBufferAction
): TextBufferState {
  const currentLine = (r: number): string => state.lines[r] ?? '';
  const currentLineLen = (r: number): number => cpLen(currentLine(r));

  switch (action.type) {
    case 'set_text': {
      const newLines = action.payload.replace(/\r\n?/g, '\n').split('\n');
      const lines = newLines.length === 0 ? [''] : newLines;
      const lastLineIndex = lines.length - 1;
      return {
        lines,
        cursorRow: lastLineIndex,
        cursorCol: cpLen(lines[lastLineIndex] ?? ''),
      };
    }

    case 'insert': {
      const newLines = [...state.lines];
      let newCursorRow = state.cursorRow;
      let newCursorCol = state.cursorCol;

      // Strip unsafe characters and normalize newlines
      const str = stripUnsafeCharacters(
        action.payload.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
      );

      if (str.length === 0) {
        return state;
      }

      const parts = str.split('\n');
      const lineContent = currentLine(newCursorRow);
      const before = cpSlice(lineContent, 0, newCursorCol);
      const after = cpSlice(lineContent, newCursorCol);

      if (parts.length > 1) {
        // Multi-line insert
        newLines[newCursorRow] = before + parts[0];
        const remainingParts = parts.slice(1);
        const lastPartOriginal = remainingParts.pop() ?? '';
        newLines.splice(newCursorRow + 1, 0, ...remainingParts);
        newLines.splice(
          newCursorRow + parts.length - 1,
          0,
          lastPartOriginal + after
        );
        newCursorRow = newCursorRow + parts.length - 1;
        newCursorCol = cpLen(lastPartOriginal);
      } else {
        // Single line insert
        newLines[newCursorRow] = before + parts[0] + after;
        newCursorCol = cpLen(before) + cpLen(parts[0]);
      }

      return {
        lines: newLines,
        cursorRow: newCursorRow,
        cursorCol: newCursorCol,
      };
    }

    case 'backspace': {
      const newLines = [...state.lines];
      let newCursorRow = state.cursorRow;
      let newCursorCol = state.cursorCol;

      if (newCursorCol === 0 && newCursorRow === 0) return state;

      if (newCursorCol > 0) {
        const lineContent = currentLine(newCursorRow);
        newLines[newCursorRow] =
          cpSlice(lineContent, 0, newCursorCol - 1) +
          cpSlice(lineContent, newCursorCol);
        newCursorCol--;
      } else if (newCursorRow > 0) {
        // Merge with previous line
        const prevLineContent = currentLine(newCursorRow - 1);
        const currentLineContent = currentLine(newCursorRow);
        const newCol = cpLen(prevLineContent);
        newLines[newCursorRow - 1] = prevLineContent + currentLineContent;
        newLines.splice(newCursorRow, 1);
        newCursorRow--;
        newCursorCol = newCol;
      }

      return {
        lines: newLines,
        cursorRow: newCursorRow,
        cursorCol: newCursorCol,
      };
    }

    case 'delete': {
      const { cursorRow, cursorCol, lines } = state;
      const lineContent = currentLine(cursorRow);

      if (cursorCol < currentLineLen(cursorRow)) {
        const newLines = [...lines];
        newLines[cursorRow] =
          cpSlice(lineContent, 0, cursorCol) +
          cpSlice(lineContent, cursorCol + 1);
        return { ...state, lines: newLines };
      } else if (cursorRow < lines.length - 1) {
        // Merge with next line
        const nextLineContent = currentLine(cursorRow + 1);
        const newLines = [...lines];
        newLines[cursorRow] = lineContent + nextLineContent;
        newLines.splice(cursorRow + 1, 1);
        return { ...state, lines: newLines };
      }
      return state;
    }

    case 'move': {
      const { dir } = action.payload;
      const { cursorRow, cursorCol, lines } = state;
      const lineLen = currentLineLen(cursorRow);

      switch (dir) {
        case 'left':
          if (cursorCol > 0) {
            return { ...state, cursorCol: cursorCol - 1 };
          } else if (cursorRow > 0) {
            return {
              ...state,
              cursorRow: cursorRow - 1,
              cursorCol: cpLen(lines[cursorRow - 1] || ''),
            };
          }
          return state;

        case 'right':
          if (cursorCol < lineLen) {
            return { ...state, cursorCol: cursorCol + 1 };
          } else if (cursorRow < lines.length - 1) {
            return { ...state, cursorRow: cursorRow + 1, cursorCol: 0 };
          }
          return state;

        case 'up':
          if (cursorRow > 0) {
            const newCol = Math.min(cursorCol, cpLen(lines[cursorRow - 1] || ''));
            return { ...state, cursorRow: cursorRow - 1, cursorCol: newCol };
          }
          return state;

        case 'down':
          if (cursorRow < lines.length - 1) {
            const newCol = Math.min(cursorCol, cpLen(lines[cursorRow + 1] || ''));
            return { ...state, cursorRow: cursorRow + 1, cursorCol: newCol };
          }
          return state;

        case 'home':
          return { ...state, cursorCol: 0 };

        case 'end':
          return { ...state, cursorCol: lineLen };

        default:
          return state;
      }
    }

    case 'newline': {
      const newLines = [...state.lines];
      const { cursorRow, cursorCol } = state;
      const lineContent = currentLine(cursorRow);
      const before = cpSlice(lineContent, 0, cursorCol);
      const after = cpSlice(lineContent, cursorCol);

      newLines[cursorRow] = before;
      newLines.splice(cursorRow + 1, 0, after);

      return {
        lines: newLines,
        cursorRow: cursorRow + 1,
        cursorCol: 0,
      };
    }

    case 'delete_word_left': {
      const { cursorRow, cursorCol } = state;
      if (cursorCol === 0 && cursorRow === 0) return state;

      const newLines = [...state.lines];
      let newCursorRow = cursorRow;
      let newCursorCol = cursorCol;

      if (cursorCol > 0) {
        const lineContent = currentLine(cursorRow);
        const codePoints = toCodePoints(lineContent);

        // Find word boundary
        let start = cursorCol;
        // Skip trailing spaces
        while (start > 0 && codePoints[start - 1] === ' ') start--;
        // Skip word characters
        while (start > 0 && codePoints[start - 1] !== ' ') start--;

        newLines[cursorRow] =
          cpSlice(lineContent, 0, start) + cpSlice(lineContent, cursorCol);
        newCursorCol = start;
      } else {
        // Act as backspace - merge with previous line
        const prevLineContent = currentLine(cursorRow - 1);
        const currentLineContent = currentLine(cursorRow);
        const newCol = cpLen(prevLineContent);
        newLines[cursorRow - 1] = prevLineContent + currentLineContent;
        newLines.splice(cursorRow, 1);
        newCursorRow--;
        newCursorCol = newCol;
      }

      return {
        lines: newLines,
        cursorRow: newCursorRow,
        cursorCol: newCursorCol,
      };
    }

    case 'kill_line_left': {
      const { cursorRow, cursorCol } = state;
      if (cursorCol === 0) return state;

      const lineContent = currentLine(cursorRow);
      const newLines = [...state.lines];
      newLines[cursorRow] = cpSlice(lineContent, cursorCol);

      return {
        lines: newLines,
        cursorRow,
        cursorCol: 0,
      };
    }

    case 'kill_line_right': {
      const { cursorRow, cursorCol, lines } = state;
      const lineContent = currentLine(cursorRow);

      if (cursorCol < currentLineLen(cursorRow)) {
        const newLines = [...lines];
        newLines[cursorRow] = cpSlice(lineContent, 0, cursorCol);
        return { ...state, lines: newLines };
      } else if (cursorRow < lines.length - 1) {
        // Merge with next line
        const nextLineContent = currentLine(cursorRow + 1);
        const newLines = [...lines];
        newLines[cursorRow] = lineContent + nextLineContent;
        newLines.splice(cursorRow + 1, 1);
        return { ...state, lines: newLines };
      }
      return state;
    }

    case 'set_cursor_absolute': {
      const position = action.payload;
      const { lines } = state;

      // Convert absolute position to row/col
      let remaining = position;
      let newRow = 0;
      let newCol = 0;

      for (let i = 0; i < lines.length; i++) {
        const lineLen = cpLen(lines[i]);
        if (remaining <= lineLen) {
          newRow = i;
          newCol = remaining;
          break;
        }
        remaining -= lineLen + 1; // +1 for newline character
        if (i === lines.length - 1) {
          // Past end of text, put cursor at end
          newRow = i;
          newCol = lineLen;
        }
      }

      return {
        ...state,
        cursorRow: newRow,
        cursorCol: newCol,
      };
    }

    default:
      return state;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Hook
// ─────────────────────────────────────────────────────────────────────────────

export interface UseTextBufferOptions {
  initialText?: string;
  onChange?: (text: string) => void;
}

export interface TextBuffer {
  // State
  lines: string[];
  text: string;
  cursor: [number, number]; // [row, col]
  absoluteCursor: number; // Absolute cursor position in text

  // Actions
  setText: (text: string) => void;
  insert: (ch: string) => void;
  newline: () => void;
  backspace: () => void;
  del: () => void;
  move: (dir: Direction) => void;
  deleteWordLeft: () => void;
  killLineLeft: () => void;
  killLineRight: () => void;
  handleInput: (key: Key) => void;
  setCursorToAbsolute: (position: number) => void;
}

export function useTextBuffer({
  initialText = '',
  onChange,
}: UseTextBufferOptions = {}): TextBuffer {
  const initialState = useMemo((): TextBufferState => {
    const lines = initialText.split('\n');
    return {
      lines: lines.length === 0 ? [''] : lines,
      cursorRow: 0,
      cursorCol: 0,
    };
  }, [initialText]);

  const [state, dispatch] = useReducer(textBufferReducer, initialState);
  const { lines, cursorRow, cursorCol } = state;

  const text = useMemo(() => lines.join('\n'), [lines]);

  // Notify onChange when text changes
  useEffect(() => {
    if (onChange) {
      onChange(text);
    }
  }, [text, onChange]);

  // Actions
  const setText = useCallback((newText: string): void => {
    dispatch({ type: 'set_text', payload: newText });
  }, []);

  const insert = useCallback((ch: string): void => {
    dispatch({ type: 'insert', payload: ch });
  }, []);

  const newline = useCallback((): void => {
    dispatch({ type: 'newline' });
  }, []);

  const backspace = useCallback((): void => {
    dispatch({ type: 'backspace' });
  }, []);

  const del = useCallback((): void => {
    dispatch({ type: 'delete' });
  }, []);

  const move = useCallback((dir: Direction): void => {
    dispatch({ type: 'move', payload: { dir } });
  }, []);

  const deleteWordLeft = useCallback((): void => {
    dispatch({ type: 'delete_word_left' });
  }, []);

  const killLineLeft = useCallback((): void => {
    dispatch({ type: 'kill_line_left' });
  }, []);

  const killLineRight = useCallback((): void => {
    dispatch({ type: 'kill_line_right' });
  }, []);

  const setCursorToAbsolute = useCallback((position: number): void => {
    dispatch({ type: 'set_cursor_absolute', payload: position });
  }, []);

  // Calculate absolute cursor position
  const absoluteCursor = useMemo(() => {
    let pos = 0;
    for (let i = 0; i < cursorRow; i++) {
      pos += cpLen(lines[i]) + 1; // +1 for newline
    }
    pos += cursorCol;
    return pos;
  }, [lines, cursorRow, cursorCol]);

  // Handle keyboard input
  const handleInput = useCallback(
    (key: Key): void => {
      const { sequence: input } = key;

      // Navigation
      if (key.name === 'left' && !key.meta && !key.ctrl) {
        move('left');
      } else if (key.name === 'right' && !key.meta && !key.ctrl) {
        move('right');
      } else if (key.name === 'up') {
        move('up');
      } else if (key.name === 'down') {
        move('down');
      } else if (key.name === 'home' || (key.ctrl && key.name === 'a')) {
        move('home');
      } else if (key.name === 'end' || (key.ctrl && key.name === 'e')) {
        move('end');
      }
      // Deletion
      // Ctrl+U: delete to beginning of line
      else if (key.ctrl && key.name === 'u') {
        killLineLeft();
      }
      // Ctrl+K: delete to end of line
      else if (key.ctrl && key.name === 'k') {
        killLineRight();
      }
      // Ctrl+W: delete word backward
      else if (key.ctrl && key.name === 'w') {
        deleteWordLeft();
      } else if (key.name === 'backspace' || input === '\x7f' || (key.ctrl && key.name === 'h')) {
        backspace();
      } else if (key.name === 'delete' || (key.ctrl && key.name === 'd')) {
        del();
      }
      // Insertable characters
      else if (key.insertable && input) {
        insert(input);
      }
    },
    [move, backspace, del, deleteWordLeft, killLineLeft, killLineRight, insert]
  );

  return useMemo(
    () => ({
      lines,
      text,
      cursor: [cursorRow, cursorCol] as [number, number],
      absoluteCursor,
      setText,
      insert,
      newline,
      backspace,
      del,
      move,
      deleteWordLeft,
      killLineLeft,
      killLineRight,
      handleInput,
      setCursorToAbsolute,
    }),
    [
      lines,
      text,
      cursorRow,
      cursorCol,
      absoluteCursor,
      setText,
      insert,
      newline,
      backspace,
      del,
      move,
      deleteWordLeft,
      killLineLeft,
      killLineRight,
      handleInput,
      setCursorToAbsolute,
    ]
  );
}
