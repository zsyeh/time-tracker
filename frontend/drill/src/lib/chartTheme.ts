function token(name: string, fallback: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

export function chartPalette() {
  return {
    text: token('--text-secondary', '#a1a8b3'),
    primary: token('--text-primary', '#e5e9ef'),
    border: token('--border-subtle', '#2b3038'),
    surface: token('--bg-elevated', '#20242b'),
    accent: token('--accent', '#6ba6ff'),
    mastered: token('--mastered', '#55b88a'),
    review: token('--review', '#d5a44f'),
  }
}

export function chartVisuals(palette: ReturnType<typeof chartPalette>) {
  return {
    animationDuration: 220,
    textStyle: { fontFamily: 'Inter, PingFang SC, sans-serif' },
    tooltip: {
      trigger: 'axis' as const,
      confine: true,
      backgroundColor: palette.surface,
      borderColor: palette.border,
      textStyle: { color: palette.primary, fontSize: 12 },
    },
  }
}
