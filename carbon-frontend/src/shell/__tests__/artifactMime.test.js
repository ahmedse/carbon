import { describe, it, expect } from 'vitest';
import { isPreviewableMime, isImageMime } from '../artifactMime';

describe('artifactMime', () => {
  it('allows true text/json/csv previews', () => {
    expect(isPreviewableMime('text/plain')).toBe(true);
    expect(isPreviewableMime('text/csv')).toBe(true);
    expect(isPreviewableMime('application/json')).toBe(true);
    expect(isPreviewableMime('text/markdown; charset=utf-8')).toBe(true);
  });

  it('never treats Office Open XML as text-previewable', () => {
    expect(
      isPreviewableMime(
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      ),
    ).toBe(false);
    expect(
      isPreviewableMime(
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      ),
    ).toBe(false);
    expect(isPreviewableMime('application/pdf')).toBe(false);
  });

  it('detects image mimes', () => {
    expect(isImageMime('image/png')).toBe(true);
    expect(isImageMime('image/jpeg')).toBe(true);
  });
});
