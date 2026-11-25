import { json } from '@codemirror/lang-json'
import { markdown } from '@codemirror/lang-markdown'
import { Decoration, EditorView, MatchDecorator, ViewPlugin, type DecorationSet, type ViewUpdate } from '@codemirror/view'
import CodeMirror from '@uiw/react-codemirror'
import { usePlatformStore } from '../../store/usePlatformStore'

const varDeco = new MatchDecorator({ regexp: /{{\s*\w+\s*}}/g, decoration: Decoration.mark({ class: 'cm-var' }) })
const varHighlight = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet
    constructor(view: EditorView) {
      this.decorations = varDeco.createDeco(view)
    }
    update(u: ViewUpdate) {
      this.decorations = varDeco.updateDeco(u, this.decorations)
    }
  },
  { decorations: (v) => v.decorations },
)

interface Props {
  value: string
  onChange?: (v: string) => void
  lang?: 'text' | 'json'
  minHeight?: string
  maxHeight?: string
  readOnly?: boolean
  label: string
}

export function PromptEditor({ value, onChange, lang = 'text', minHeight = '120px', maxHeight = '520px', readOnly = false, label }: Props) {
  const dark = usePlatformStore((s) => s.dark)
  return (
    <div className="overflow-hidden rounded-lg border border-line focus-within:border-teal-dk dark:border-night-line" aria-label={label}>
      <CodeMirror
        value={value}
        onChange={onChange}
        readOnly={readOnly}
        theme={dark ? 'dark' : 'light'}
        minHeight={minHeight}
        maxHeight={maxHeight}
        basicSetup={{ lineNumbers: true, foldGutter: false, highlightActiveLine: !readOnly, autocompletion: false }}
        extensions={[lang === 'json' ? json() : markdown(), varHighlight, EditorView.lineWrapping, EditorView.contentAttributes.of({ 'aria-label': label })]}
      />
    </div>
  )
}
