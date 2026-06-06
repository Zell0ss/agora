export const Ico = {
  plus:     'M10 4v12M4 10h12',
  search:   'M9 3a6 6 0 104.2 10.3L17 17M9 3a6 6 0 014.2 10.3',
  send:     'M4 10l13-6-6 13-2.2-4.8L4 10z',
  round:    'M16 5v4h-4M15.5 9A6 6 0 105 13',
  export:   'M10 3v9m0-9L7 6m3-3l3 3M4 13v2.5A1.5 1.5 0 005.5 17h9a1.5 1.5 0 001.5-1.5V13',
  userplus: 'M12.5 16v-1.5A2.5 2.5 0 0010 12H5.5A2.5 2.5 0 003 14.5V16M7.75 9a2.5 2.5 0 100-5 2.5 2.5 0 000 5M16 6v4M18 8h-4',
  chevron:  'M5 8l5 5 5-5',
  copy:     'M7 7V4.5A1.5 1.5 0 018.5 3h7A1.5 1.5 0 0117 4.5v7a1.5 1.5 0 01-1.5 1.5H13M11.5 7h-7A1.5 1.5 0 003 8.5v7A1.5 1.5 0 004.5 17h7a1.5 1.5 0 001.5-1.5v-7A1.5 1.5 0 0011.5 7z',
  download: 'M10 3v9m0 0l3.2-3.2M10 12L6.8 8.8M4 15.5h12',
  check:    'M4 10.5l4 4 8-9',
  warn:     'M10 3.5l7 12H3l7-12zM10 8.5v3.5M10 14.2v.2',
  sun:      ['M10 7.2a2.8 2.8 0 100 5.6 2.8 2.8 0 000-5.6',
             'M10 2.6v1.8M10 15.6v1.8M2.6 10h1.8M15.6 10h1.8M4.8 4.8l1.3 1.3M13.9 13.9l1.3 1.3M15.2 4.8l-1.3 1.3M6.1 13.9l-1.3 1.3'],
  moon:     'M15.4 11.3A6 6 0 117.7 3.6 4.8 4.8 0 0015.4 11.3z',
}

export default function Icon({ d, size = 20, stroke = 1.6, fill = 'none', style }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 20 20"
      fill={fill}
      stroke={fill === 'none' ? 'currentColor' : 'none'}
      strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
      style={{ flex: '0 0 auto', ...style }}
    >
      {(Array.isArray(d) ? d : [d]).map((p, i) => <path key={i} d={p} />)}
    </svg>
  )
}
