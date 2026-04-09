import React from 'react';
import { HighlightedText } from './highlighter';

export function highlightText(text, query) {
  return <HighlightedText text={text} query={query} />;
}
