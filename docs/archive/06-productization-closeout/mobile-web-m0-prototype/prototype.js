const viewport = document.querySelector('#phoneViewport')
const phone = document.querySelector('#phone')
const frameLabel = document.querySelector('#frameLabel')
const themeButton = document.querySelector('#themeButton')
const toast = document.querySelector('#toast')

const screens = new Set(['home', 'stats', 'ranking', 'billboard', 'detail', 'ai'])
let currentScreen = 'home'
let toastTimer = null

const sheetContent = {
  'analysis-sections': {
    title: '播放分析栏目',
    options: [
      ['播放统计', '时间、频率和分布', 'stats'],
      ['播放排行', '歌曲、专辑和艺人榜', 'ranking'],
      ['年度总结', '纵向年度故事', null],
      ['播放记录', '个人纪录与高光', null],
      ['账号中心', '收藏与收听习惯', null],
    ],
  },
  'billboard-sections': {
    title: '个人 Billboard',
    options: [
      ['周榜', '每周歌曲、专辑和艺人排名', 'billboard'],
      ['每周榜首', '冠军时间线', null],
      ['年榜', 'Year-End 成绩', null],
      ['总榜', '完整历史成绩', null],
      ['榜单记录', '冠军、长寿与突破纪录', null],
      ['对决', '并排比较 2–4 个实体', null],
    ],
  },
  time: {
    title: '选择时间范围',
    options: [
      ['全部时间', '2022-06-24 至 2026-07-24', null],
      ['最近 6 个月', '滚动时间窗口', null],
      ['最近 4 周', '观察近期变化', null],
      ['年份 / 月份 / 周', '进入精确选择器', null],
      ['自定义范围', '选择开始和结束日期', null],
    ],
  },
  week: {
    title: '选择榜单周',
    options: [
      ['Week 29, 2026', '7 月 17 日 — 7 月 23 日', null],
      ['Week 28, 2026', '7 月 10 日 — 7 月 16 日', null],
      ['Week 27, 2026', '7 月 3 日 — 7 月 9 日', null],
      ['浏览全部周次', '按年份和月份定位', null],
    ],
  },
  filters: {
    title: '筛选与显示',
    options: [
      ['当前范围', '全部时间', null],
      ['有效播放口径', '动态阈值 · 连续播放合并', null],
      ['排序', '按主要指标降序', null],
      ['重置筛选', '恢复当前页面默认值', null],
    ],
  },
  metric: {
    title: '选择主要指标',
    options: [
      ['播放次数', '按有效播放事件排序', null],
      ['播放时长', '按累计有效时长排序', null],
    ],
  },
  'more-stats': {
    title: '更多统计',
    facts: [
      ['日均播放', '44 次'],
      ['日均时长', '2.8 小时'],
      ['独特专辑', '1,966 张'],
      ['活跃天数', '1,467 天'],
    ],
  },
  entity: {
    title: '完整数据',
    copy: '移动榜单默认只保留主指标和两个次级事实，完整字段在此查看；这些字段的隐藏不会改变原始排名。',
    facts: [
      ['播放次数', '376'],
      ['播放时长', '22.4 小时'],
      ['首次播放', '2023-06-30'],
      ['最近播放', '2026-06-14'],
      ['个人榜最高', '#1'],
      ['在榜周数', '48 周'],
    ],
  },
  evidence: {
    title: '回答依据',
    copy: 'AI 只使用项目允许的只读工具，回答中的变化结论由以下证据共同支持。',
    facts: [
      ['时间范围', '2026 夏季 vs 2025 夏季'],
      ['时间分布', '午间播放 +28%'],
      ['回听占比', '54% → 63%'],
      ['语言分布', '仅使用 approved 事实'],
    ],
  },
  history: {
    title: '对话历史',
    options: [
      ['今年夏天的变化', '刚刚', null],
      ['最近重听的专辑', '昨天', null],
      ['2025 年度总结', '7 月 28 日', null],
      ['开始新对话', '清空当前上下文', null],
    ],
  },
  settings: {
    title: '快速设置',
    options: [
      ['外观与名称', '主题、简繁体和榜单名称', null],
      ['播放过滤', '动态阈值与连续播放', null],
      ['Billboard 参数', 'Top N 与周起点', null],
      ['高级管理', '请在电脑端完成', null],
    ],
  },
  'detail-more': {
    title: '更多操作',
    options: [
      ['分享详情', '复制当前可分享链接', null],
      ['管理曲目信息', '手机显示摘要，电脑端编辑', null],
      ['查看所属专辑', 'GUTS · Olivia Rodrigo', null],
    ],
  },
  chart: {
    title: '全屏图表',
    copy: '正式实现中，此操作会进入无全局导航的横向或纵向全屏图表层；tooltip 改为点击触发。',
    facts: [
      ['交互', '点按 tooltip'],
      ['缩放', '仅长时间序列启用'],
      ['退出', '固定关闭按钮 / 系统返回'],
    ],
  },
  'chart-help': {
    title: '个人 Billboard 说明',
    copy: '榜单只基于你的有效播放历史，并非外部官方 Billboard。移动版和电脑端使用同一统计口径与过滤指纹。',
    facts: [
      ['本周边界', '周五 12:00'],
      ['歌曲榜容量', 'Top 30'],
      ['合并级别', 'L2 录音版本'],
    ],
  },
}

function showToast(message) {
  toast.textContent = message
  toast.classList.add('is-visible')
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => toast.classList.remove('is-visible'), 2200)
}

function updateScreenRail() {
  document.querySelectorAll('.screen-tab').forEach((button) => {
    button.classList.toggle('is-active', button.dataset.screen === currentScreen)
  })
}

function renderScreen(name, { preserveTheme = true } = {}) {
  if (!screens.has(name)) {
    showToast('该入口属于完整页面范围，本原型只展示六个代表页面。')
    return
  }

  const template = document.querySelector(`#screen-${name}`)
  if (!template) return
  const wasDark = phone.classList.contains('is-dark')
  viewport.replaceChildren(template.content.cloneNode(true))
  currentScreen = name
  updateScreenRail()
  if (preserveTheme && wasDark) phone.classList.add('is-dark')
}

function closeSheet() {
  viewport.querySelector('.sheet-backdrop')?.remove()
  viewport.querySelector('.bottom-sheet')?.remove()
}

function renderSheetBody(config, key) {
  if (config.options) {
    const options = config.options.map(([label, description, screen], index) => {
      const active =
        (key === 'analysis-sections' && ((currentScreen === 'stats' && index === 0) || (currentScreen === 'ranking' && index === 1))) ||
        (key === 'billboard-sections' && index === 0) ||
        ((key === 'time' || key === 'week' || key === 'metric') && index === 0)
      return `
        <button type="button" class="sheet-option${active ? ' is-active' : ''}" ${screen ? `data-sheet-screen="${screen}"` : 'data-sheet-placeholder'}>
          <b>${label}</b><small>${description}</small><span>${active ? '✓' : '›'}</span>
        </button>`
    }).join('')
    return `<div class="sheet-options">${options}</div>`
  }

  const facts = (config.facts || []).map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join('')
  return `${config.copy ? `<p class="sheet-copy">${config.copy}</p>` : ''}<dl class="sheet-facts">${facts}</dl>`
}

function openSheet(key) {
  const config = sheetContent[key]
  if (!config) return
  closeSheet()
  const template = document.querySelector('#sheet-template')
  const fragment = template.content.cloneNode(true)
  fragment.querySelector('#sheetTitle').textContent = config.title
  fragment.querySelector('#sheetBody').innerHTML = renderSheetBody(config, key)
  viewport.append(fragment)
  viewport.querySelector('.bottom-sheet button, .sheet-option')?.focus()
}

document.addEventListener('click', (event) => {
  const target = event.target.closest('button, a')
  if (!target) return

  if (target.matches('[data-close-sheet]')) {
    closeSheet()
    return
  }

  if (target.dataset.openSheet) {
    openSheet(target.dataset.openSheet)
    return
  }

  if (target.dataset.sheetScreen) {
    closeSheet()
    renderScreen(target.dataset.sheetScreen)
    return
  }

  if (target.hasAttribute('data-sheet-placeholder') || target.dataset.placeholder) {
    closeSheet()
    showToast(target.dataset.placeholder ? `${target.dataset.placeholder}不在六屏原型中，完整规格已保留。` : '该页面已纳入完整设计规格，本轮不制作额外画板。')
    return
  }

  if (target.dataset.screen) {
    if (screens.has(target.dataset.screen)) renderScreen(target.dataset.screen)
    else showToast('搜索页已纳入完整规格，本轮使用音乐详情代表推入层。')
    return
  }

  if (target.closest('.segmented, .mini-switch, .mode-switch')) {
    const group = target.parentElement
    group.querySelectorAll('button').forEach((button) => button.classList.remove('is-active'))
    target.classList.add('is-active')
  }
})

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeSheet()
})

document.querySelectorAll('[data-frame]').forEach((button) => {
  button.addEventListener('click', () => {
    const width = button.dataset.frame
    document.documentElement.style.setProperty('--phone-width', `${width}px`)
    document.querySelectorAll('[data-frame]').forEach((item) => item.classList.toggle('is-active', item === button))
    frameLabel.textContent = `${width} × 844`
  })
})

themeButton.addEventListener('click', () => {
  phone.classList.toggle('is-dark')
  showToast(phone.classList.contains('is-dark') ? '已切换到夜间主题' : '已切换到白日主题')
})

renderScreen('home', { preserveTheme: false })
