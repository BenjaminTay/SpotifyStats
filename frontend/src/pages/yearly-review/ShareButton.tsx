import { useState } from 'react'

export function ShareButton() {
  const [generating, setGenerating] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const { toPng } = await import('html-to-image')
      const el = document.querySelector('.yearly-review-content') as HTMLElement
      if (!el) {
        alert('页面内容未加载完成')
        return
      }
      const dataUrl = await toPng(el, {
        backgroundColor: document.documentElement.classList.contains('dark') ? '#0a0a0a' : '#fafafa',
        pixelRatio: 2,
        cacheBust: true,
      })
      setPreview(dataUrl)
    } catch (err) {
      console.error('Failed to generate image:', err)
      alert('生成图片失败，请重试')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <>
      {/* 浮动按钮 */}
      <button
        onClick={handleGenerate}
        disabled={generating}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-2.5 rounded-full bg-accent-foreground text-card font-sans text-[13px] font-semibold shadow-lg hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        {generating ? (
          <>
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            生成中...
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            生成长图
          </>
        )}
      </button>

      {/* 预览弹窗 */}
      {preview && (
        <div
          className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setPreview(null)}
        >
          <div className="relative max-w-md max-h-[90vh] overflow-auto rounded-xl" onClick={e => e.stopPropagation()}>
            <img src={preview} alt="年度总结长图" className="w-full" />
            <button
              onClick={() => setPreview(null)}
              className="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/50 text-white flex items-center justify-center hover:bg-black/70 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <p className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/60 text-white text-[12px] px-3 py-1.5 rounded-full">
              长按或右键保存图片
            </p>
          </div>
        </div>
      )}
    </>
  )
}
