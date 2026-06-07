/**
 * renderer.test.js — PPT slide renderer unit tests
 *
 * Run with: npx vitest
 */

import { describe, test, expect } from 'vitest';
import { SlideRenderer, renderSlide, hasSlideRenderer } from '../../js/templates/ppt/renderer.js';

// Import all slide types so they register
import '../../js/templates/ppt/slides/cover.js';
import '../../js/templates/ppt/slides/chart-donut.js';
import '../../js/templates/ppt/slides/quote.js';

const mockTpl = {
  v: { style: 'engraved', bg: '#111318', a: '#c96442', dark: true }
};

describe('SlideRenderer base class', () => {
  test('extracts colors from template', () => {
    const slide = { type: 'cover', title: 'Test' };
    const r = new SlideRenderer(mockTpl, slide);
    expect(r.dark).toBe(true);
    expect(r.bg).toBe('#111318');
    expect(r.accent).toBe('#c96442');
  });

  test('escapes HTML in user input', () => {
    const slide = { type: 'cover', title: '<script>alert(1)</script>' };
    const r = new SlideRenderer(mockTpl, slide);
    const html = r.renderContent();
    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
  });
});

describe('Registry', () => {
  test('hasSlideRenderer returns true for registered types', () => {
    expect(hasSlideRenderer('cover')).toBe(true);
    expect(hasSlideRenderer('chart-donut')).toBe(true);
    expect(hasSlideRenderer('nonexistent')).toBe(false);
  });
});

describe('renderSlide', () => {
  test('renders a cover slide without errors', () => {
    const slide = {
      type: 'cover',
      title: 'Q1 经营分析',
      subtitle: '深度研究报告',
      eyebrow: 'CONFIDENTIAL',
    };
    const html = renderSlide(mockTpl, slide);
    expect(html).toContain('Q1 经营分析');
    expect(html).toContain('container-type:inline-size');
  });

  test('renders a chart-donut slide', () => {
    const slide = {
      type: 'chart-donut',
      eyebrow: '构成',
      title: '核心构成',
      segments: [{ label: 'A', value: '45%' }, { label: 'B', value: '55%' }],
    };
    const html = renderSlide(mockTpl, slide);
    expect(html).toContain('conic-gradient');
    expect(html).toContain('45%');
  });

  test('XSS protection: malicious payload is escaped', () => {
    const slide = {
      type: 'quote',
      title: '标题',
      quote: '<img src=x onerror=alert(1)>',
      author: 'Author',
    };
    const html = renderSlide(mockTpl, slide);
    expect(html).not.toContain('onerror');
    expect(html).not.toContain('<img src=x');
    expect(html).toContain('&lt;img');
  });
});
