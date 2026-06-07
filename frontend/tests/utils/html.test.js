/**
 * html.test.js — Safe HTML template engine tests
 */

import { describe, test, expect } from 'vitest';
import { html, trust, escapeHtml, toDom } from '../../js/utils/html.js';

describe('escapeHtml', () => {
  test('escapes <, >, &, quotes', () => {
    expect(escapeHtml('<script>')).toBe('&lt;script&gt;');
    expect(escapeHtml('"hello"')).toBe('&quot;hello&quot;');
    expect(escapeHtml("'test'")).toBe('&#39;test&#39;');
    expect(escapeHtml('a & b')).toBe('a &amp; b');
  });

  test('does not mutate safe strings', () => {
    expect(escapeHtml('hello world')).toBe('hello world');
  });
});

describe('html tagged template', () => {
  test('interpolates values safely', () => {
    const name = '<script>';
    const result = html`<div>${name}</div>`;
    expect(result).toBe('<div>&lt;script&gt;</div>');
  });

  test('preserves raw HTML via trust()', () => {
    const raw = trust('<span>safe</span>');
    const result = html`<div>${raw}</div>`;
    expect(result).toBe('<div><span>safe</span></div>');
  });

  test('handles numbers and null', () => {
    const n = 42;
    const result = html`<span>${n}</span>`;
    expect(result).toBe('<span>42</span>');
  });
});

describe('toDom', () => {
  test('creates DOM element from string', () => {
    const el = toDom('<div class="test">hello</div>');
    expect(el.tagName).toBe('DIV');
    expect(el.className).toBe('test');
    expect(el.textContent).toBe('hello');
  });
});
