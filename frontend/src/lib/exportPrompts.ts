import type { AgentDef, ToolSpec } from '../types'

// Formato .txt de la sección 13 del SPEC.
export function exportTxt(agents: AgentDef[], tools: ToolSpec[], version: number | null): string {
  const escritura = new Set(tools.filter((t) => t.escritura).map((t) => t.name))
  const head = [
    'AGENT EXPLORER PLATFORM · PROMPTS DE AGENTES · Sesión 4 · AI Context & Vibe Engineering 2026 (UAI + XeraX)',
    `versión de agentes: ${version ?? '—'} · exportado: ${new Date().toISOString()}`,
    '='.repeat(96),
    '',
  ]
  const body = agents.map((a, i) => {
    const vars = a.prompt.variables.map((v) => `${v.nombre}: ${v.descripcion} · ${v.origen} · ej: ${v.ejemplo}`).join('\n')
    const tl = a.tools.map((t) => `${t} (${escritura.has(t) || a.acciones_escritura.includes(t) ? 'escritura·confirmación' : 'lectura'})`).join(', ') || '—'
    const l = a.limits
    return [
      `############## ${i + 1} · ${a.id.toUpperCase()} · ${a.tipo.toUpperCase()} · ${a.nombre} ##############`,
      '--- SYSTEM ---',
      a.prompt.system,
      '--- USER ---',
      a.prompt.user,
      '--- VARIABLES ---',
      vars,
      '--- TOOLS ---',
      tl,
      '--- LÍMITES ---',
      `max_iters=${l.max_iters} · max_tokens_out=${l.max_tokens_out} · timeout_s=${l.timeout_s} · temperature=${l.temperature} · modelo=${l.modelo ?? 'OPENAI_MODEL'}`,
      '--- SALIDA ESPERADA ---',
      a.prompt.salida_esperada,
      '',
    ].join('\n')
  })
  return [...head, ...body].join('\n')
}

export function exportMd(agents: AgentDef[]): string {
  const parts = ['# Agent Explorer Platform — prompts de agentes', '', `_Exportado: ${new Date().toISOString()}_`, '']
  for (const a of agents) {
    parts.push(`## ${a.nombre} \`${a.id}\` · ${a.tipo}`, '', `> ${a.tagline}`, '', a.descripcion, '')
    if (a.tools.length) parts.push(`**Tools:** ${a.tools.map((t) => `\`${t}\``).join(', ')}`, '')
    parts.push('### System', '', '```text', a.prompt.system, '```', '', '### User', '', '```text', a.prompt.user, '```', '')
    parts.push('### Variables', '', '| nombre | origen | descripción | ejemplo |', '|---|---|---|---|')
    for (const v of a.prompt.variables) parts.push(`| \`${v.nombre}\` | ${v.origen} | ${v.descripcion} | ${v.ejemplo.replace(/\|/g, '\\|')} |`)
    parts.push('', '### Salida esperada', '', '```text', a.prompt.salida_esperada, '```', '')
  }
  return parts.join('\n')
}

export function download(name: string, content: string, mime = 'text/plain') {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
