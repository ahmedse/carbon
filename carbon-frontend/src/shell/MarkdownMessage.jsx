// src/shell/MarkdownMessage.jsx
// ────────────────────────────────────────────────────────────────────────────
// GENERIC RICH MARKDOWN RENDERER for AI assistant messages.
//
// One renderer, driven purely by the markdown content — nothing here is
// crafted for a single feature or use case. Any assistant reply (capability
// listings, query results, explanations, reports) renders the same formal,
// Copilot-style document:
//
//   * GFM tables            — MUI Table (striped, scrollable)
//   * syntax highlighting   — rehype-highlight (One Dark theme)
//   * code snippets         — dark fenced block + language badge + copy
//   * diagrams              — ```mermaid fenced blocks → rendered SVG
//   * math                  — $$...$$ / $...$ via KaTeX
//   * figures               — images with optional title → caption
//   * smart links           — internal safe routes → SPA <Link>; else new tab
//   * task lists, blockquotes, hr — GFM
//
// Dependencies: react-markdown, remark-gfm, remark-math, rehype-highlight,
// rehype-katex, katex, mermaid (dynamic import — not in the main bundle).
// ────────────────────────────────────────────────────────────────────────────
import React, { useCallback, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import { Link as RouterLink } from 'react-router-dom';
import 'highlight.js/styles/atom-one-dark.css';
import 'katex/dist/katex.min.css';
import {
  Box,
  Checkbox,
  Chip,
  Divider,
  IconButton,
  Link,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { isSafeInternalRoute } from '../utils/navigation';

// ── Helpers ──────────────────────────────────────────────────────────────

/** Flatten React children (incl. hljs span elements) to plain text. */
function flattenText(node) {
  if (node == null || typeof node === 'boolean') return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(flattenText).join('');
  if (React.isValidElement(node)) return flattenText(node.props?.children);
  return '';
}

// ── Mermaid diagram (```mermaid) — lazily imports the heavy lib ──────────

const mermaidIdRef = { current: 0 };

function MermaidBlock({ code }) {
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import('mermaid')).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'loose',
          theme: 'default',
          fontFamily: 'inherit',
        });
        mermaidIdRef.current += 1;
        const id = `mmd-${mermaidIdRef.current}-${Date.now()}`;
        const { svg: rendered } = await mermaid.render(id, code);
        if (!cancelled) setSvg(rendered);
      } catch (err) {
        if (!cancelled) {
          setError(err?.message ? String(err.message) : 'Diagram render failed');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (error) {
    return (
      <Box sx={{ my: 1.5, borderRadius: 1, border: 1, borderColor: 'warning.main', overflow: 'hidden' }}>
        <Chip
          size="small"
          color="warning"
          variant="outlined"
          label="Diagram could not be rendered"
          sx={{ m: 0.75 }}
        />
        <Box component="pre" sx={{ m: 0, p: 1.5, bgcolor: '#282c34', overflowX: 'auto', fontSize: '0.8125rem', color: '#abb2bf' }}>
          <code>{code}</code>
        </Box>
      </Box>
    );
  }

  if (!svg) {
    return (
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', my: 1 }}>
        Rendering diagram…
      </Typography>
    );
  }

  return (
    <Box
      sx={{
        my: 1.5,
        overflowX: 'auto',
        bgcolor: 'background.paper',
        borderRadius: 1,
        border: 1,
        borderColor: 'divider',
        p: 1.5,
        '& svg': { maxWidth: '100%', height: 'auto' },
        '& a': { color: 'primary.main' },
      }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

// ── Fenced code block: dark bg + language badge + copy button ────────────

function CodeBlock({ children, className }) {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || '');
  const code = flattenText(children).replace(/\n$/, '');

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  if (!match) {
    // inline code
    return (
      <Typography
        component="code"
        sx={{
          fontFamily: 'monospace',
          fontSize: '0.85em',
          bgcolor: 'action.hover',
          px: 0.5,
          py: 0.125,
          borderRadius: 0.5,
          wordBreak: 'break-all',
        }}
      >
        {children}
      </Typography>
    );
  }

  // ```mermaid → live diagram (the generic renderer, not a bespoke card)
  if (match[1] === 'mermaid') {
    return <MermaidBlock code={code} />;
  }

  return (
    <Box sx={{ position: 'relative', my: 1.5, borderRadius: 1, overflow: 'hidden', border: 1, borderColor: 'divider' }}>
      {/* header bar */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.5,
          py: 0.5,
          bgcolor: '#21252b',
        }}
      >
        <Typography variant="caption" sx={{ color: '#9da5b4', fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {match[1]}
        </Typography>
        <Tooltip title={copied ? 'Copied!' : 'Copy code'}>
          <IconButton size="small" onClick={handleCopy} aria-label="Copy code" sx={{ color: '#9da5b4', p: 0.25 }}>
            {copied ? <CheckIcon sx={{ fontSize: 13 }} /> : <ContentCopyIcon sx={{ fontSize: 13 }} />}
          </IconButton>
        </Tooltip>
      </Box>
      {/* code body — children preserve rehype-highlight spans (syntax colors) */}
      <Box
        component="pre"
        sx={{
          m: 0,
          p: 1.5,
          bgcolor: '#282c34',
          overflowX: 'auto',
          fontFamily: 'monospace',
          fontSize: '0.8125rem',
          lineHeight: 1.6,
          color: '#abb2bf',
          '& code': { fontFamily: 'inherit', fontSize: 'inherit', bgcolor: 'transparent', p: 0 },
        }}
      >
        <code className={className}>{children}</code>
      </Box>
    </Box>
  );
}

// ── Component overrides ───────────────────────────────────────────────────────

const components = {
  // code: handles both inline and fenced blocks
  code: CodeBlock,

  // strip the default <pre> wrapper — CodeBlock renders its own container
  pre: ({ children }) => <>{children}</>,

  // paragraphs
  p: ({ children }) => (
    <Typography variant="body2" sx={{ mb: 1, '&:last-child': { mb: 0 }, lineHeight: 1.65 }}>
      {children}
    </Typography>
  ),

  // headings
  h1: ({ children }) => <Typography variant="h6" sx={{ fontWeight: 700, mt: 2, mb: 0.5 }}>{children}</Typography>,
  h2: ({ children }) => <Typography variant="subtitle1" sx={{ fontWeight: 700, mt: 1.5, mb: 0.5 }}>{children}</Typography>,
  h3: ({ children }) => <Typography variant="subtitle2" sx={{ fontWeight: 700, mt: 1, mb: 0.5 }}>{children}</Typography>,
  h4: ({ children }) => <Typography variant="body1" sx={{ fontWeight: 700, mt: 0.75, mb: 0.25 }}>{children}</Typography>,
  h5: ({ children }) => <Typography variant="body2" sx={{ fontWeight: 700, mt: 0.5, mb: 0.25 }}>{children}</Typography>,
  h6: ({ children }) => <Typography variant="caption" sx={{ fontWeight: 700, display: 'block', mt: 0.5, mb: 0.25 }}>{children}</Typography>,

  // lists
  ul: ({ children }) => <Box component="ul" sx={{ pl: 2.5, my: 0.5, mb: 1 }}>{children}</Box>,
  ol: ({ children }) => <Box component="ol" sx={{ pl: 2.5, my: 0.5, mb: 1 }}>{children}</Box>,
  li: ({ children, checked }) => {
    if (checked !== null && checked !== undefined) {
      return (
        <Box component="li" sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5, listStyle: 'none', ml: -2 }}>
          <Checkbox size="small" checked={!!checked} disabled sx={{ p: 0, mt: 0.125 }} />
          <Typography variant="body2" component="span">{children}</Typography>
        </Box>
      );
    }
    return <Typography component="li" variant="body2" sx={{ mb: 0.25 }}>{children}</Typography>;
  },

  // tables — MUI Table
  table: ({ children }) => (
    <Box sx={{ overflowX: 'auto', my: 1.5, borderRadius: 1, border: 1, borderColor: 'divider' }}>
      <Table size="small" sx={{ minWidth: 300 }}>{children}</Table>
    </Box>
  ),
  thead: ({ children }) => <TableHead sx={{ bgcolor: 'action.hover' }}>{children}</TableHead>,
  tbody: ({ children }) => <TableBody>{children}</TableBody>,
  tr: ({ children }) => <TableRow sx={{ '&:nth-of-type(even)': { bgcolor: 'action.hover' } }}>{children}</TableRow>,
  th: ({ children }) => (
    <TableCell sx={{ fontWeight: 700, fontSize: '0.8125rem', whiteSpace: 'nowrap', py: 0.75 }}>
      {children}
    </TableCell>
  ),
  td: ({ children }) => (
    <TableCell sx={{ fontSize: '0.8125rem', py: 0.75 }}>{children}</TableCell>
  ),

  // blockquote
  blockquote: ({ children }) => (
    <Box
      sx={{
        borderLeft: 3,
        borderColor: 'primary.main',
        pl: 2,
        py: 0.5,
        my: 1,
        bgcolor: 'action.hover',
        borderRadius: '0 4px 4px 0',
        color: 'text.secondary',
      }}
    >
      {children}
    </Box>
  ),

  // inline formatting
  strong: ({ children }) => <Typography component="strong" variant="inherit" sx={{ fontWeight: 700 }}>{children}</Typography>,
  em: ({ children }) => <Typography component="em" variant="inherit" sx={{ fontStyle: 'italic' }}>{children}</Typography>,
  del: ({ children }) => <Typography component="del" variant="inherit" sx={{ textDecoration: 'line-through', color: 'text.secondary' }}>{children}</Typography>,

  // links — SPA <Link> for safe internal routes, new tab otherwise
  a: ({ href, children }) => {
    if (href && href.startsWith('/') && isSafeInternalRoute(href)) {
      return (
        <Link component={RouterLink} to={href} underline="hover" sx={{ fontWeight: 500 }}>
          {children}
        </Link>
      );
    }
    return (
      <Link href={href} target="_blank" rel="noopener noreferrer" underline="hover">
        {children}
      </Link>
    );
  },

  // figures — image with optional title → caption
  img: ({ src, alt, title }) => (
    <Box sx={{ my: 1 }}>
      <Box
        component="img"
        src={src}
        alt={alt || ''}
        title={title}
        sx={{ maxWidth: '100%', borderRadius: 1, display: 'block' }}
      />
      {title && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5, textAlign: 'center' }}>
          {title}
        </Typography>
      )}
    </Box>
  ),

  // horizontal rule
  hr: () => <Divider sx={{ my: 2 }} />,
};

// ── Public component ──────────────────────────────────────────────────────────

export default function MarkdownMessage({ content }) {
  return (
    <Box sx={{ '& > *:first-of-type': { mt: 0 }, '& > *:last-of-type': { mb: 0 } }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeHighlight, rehypeKatex]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </Box>
  );
}
