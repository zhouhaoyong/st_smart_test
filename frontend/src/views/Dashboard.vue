<template>
  <div class="dashboard">
    <div class="dashboard-hero">
      <div class="hero-brand">
        <svg width="52" height="52" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" class="hero-logo">
          <defs>
            <linearGradient id="hg" x1="0" y1="40" x2="40" y2="0">
              <stop offset="0%" stop-color="#1677ff"/>
              <stop offset="100%" stop-color="#722ed1"/>
            </linearGradient>
          </defs>
          <path d="M24 4 L12 22 L18 22 L14 36 L30 18 L22 18 Z" fill="url(#hg)"/>
        </svg>
        <h1>智测</h1>
      </div>
      <p>综合性测试与开发工具平台 — 测试工作台 · API 测试 · 开发工具箱 · 导航管理</p>
    </div>

    <div class="module-grid">
      <!-- 测试工作台 -->
      <div class="module-card module-workbench" role="link" tabindex="0" aria-label="进入测试工作台" @click="$router.push('/test-workbench')" @keydown.enter="$router.push('/test-workbench')">
        <div class="card-top">
          <div class="card-icon"><el-icon :size="26"><Connection /></el-icon></div>
          <div class="card-heading">
            <h3>测试工作台</h3>
            <p>AI 辅助需求整理、用例生成、Bug 和遗留项沉淀</p>
          </div>
          <div class="card-entry" aria-hidden="true"><span>进入</span><el-icon :size="16"><ArrowRight /></el-icon></div>
        </div>
        <div class="card-tags">
          <span v-for="t in workbenchTags" :key="t" class="card-tag">{{ t }}</span>
        </div>
      </div>

      <!-- API 测试 -->
      <div class="module-card module-api" role="link" tabindex="0" aria-label="进入 API 测试" @click="$router.push('/projects')" @keydown.enter="$router.push('/projects')">
        <div class="card-top">
          <div class="card-icon"><el-icon :size="26"><VideoPlay /></el-icon></div>
          <div class="card-heading">
            <h3>API 测试</h3>
            <p>自动化接口测试平台，覆盖完整测试生命周期</p>
          </div>
          <div class="card-entry" aria-hidden="true"><span>进入</span><el-icon :size="16"><ArrowRight /></el-icon></div>
        </div>
        <div class="card-tags">
          <span v-for="t in apiTags" :key="t" class="card-tag">{{ t }}</span>
        </div>
      </div>

      <!-- 工具箱 -->
      <div class="module-card module-tools" role="link" tabindex="0" aria-label="进入工具箱" @click="$router.push('/tools/codec')" @keydown.enter="$router.push('/tools/codec')">
        <div class="card-top">
          <div class="card-icon"><el-icon :size="26"><Postcard /></el-icon></div>
          <div class="card-heading">
            <h3>工具箱</h3>
            <p>日常开发必备工具集，持续扩展中</p>
          </div>
          <div class="card-entry" aria-hidden="true"><span>进入</span><el-icon :size="16"><ArrowRight /></el-icon></div>
        </div>
        <div class="card-tags">
          <span v-for="(t, i) in toolTags" :key="i" class="card-tag card-tag--link" role="link" tabindex="0" :aria-label="`打开${t}`" @click.stop="$router.push(toolTagRouteMap[t])" @keydown.enter.stop="$router.push(toolTagRouteMap[t])">{{ t }}</span>
        </div>
      </div>

      <!-- 导航管理 -->
      <div class="module-card module-nav" role="link" tabindex="0" aria-label="进入导航管理" @click="$router.push('/tools/navigation')" @keydown.enter="$router.push('/tools/navigation')">
        <div class="card-top">
          <div class="card-icon"><el-icon :size="26"><Guide /></el-icon></div>
          <div class="card-heading">
            <h3>导航管理</h3>
            <p>集中管理常用链接，快速跳转</p>
          </div>
          <div class="card-entry" aria-hidden="true"><span>进入</span><el-icon :size="16"><ArrowRight /></el-icon></div>
        </div>
        <div class="card-tags">
          <span v-for="n in navTags" :key="n.label" class="card-tag card-tag--link" role="link" tabindex="0" :aria-label="`打开${n.label}`" @click.stop="$router.push(n.path)" @keydown.enter.stop="$router.push(n.path)">{{ n.label }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ArrowRight, VideoPlay, Guide, Postcard, Connection } from '@element-plus/icons-vue'

const workbenchTags = ['需求录入', 'AI追问', '结构化需求', '测试用例', 'Bug记录', '遗留项']
const apiTags = ['项目管理', '数据看板', '接口管理', '用例管理', '参数集', '执行集', '测试报告']
const toolTags = ['编解码工具', '文本工具', '格式处理', '生成工具', 'cURL解析', '二维码生成', '用例工具']
const navTags = [
  { label: '导航列表', path: '/tools/navigation' },
  { label: '快速跳转', path: '/tools/navigation' },
  { label: '可配置', path: '/tools/navigation' },
  { label: '轻量化', path: '/tools/navigation' },
  { label: '多入口', path: '/tools/navigation' },
  { label: '统一管理', path: '/tools/navigation' },
]

const toolTagRouteMap = {
  '编解码工具': '/tools/codec',
  '文本工具': '/tools/text-tools',
  '格式处理': '/tools/format',
  '生成工具': '/tools/generate',
  'cURL解析': '/tools/curl',
  '二维码生成': '/tools/qrcode',
  '用例工具': '/tools/xmind',
}
</script>

<style scoped>
.dashboard {
  width: 100%; max-width: 1120px;
  margin: 0 auto; padding: 0 24px 40px;
}

/* Hero */
.dashboard-hero { text-align: center; padding: 52px 0 24px; }
.hero-brand { display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 8px; }
.hero-logo { width: 50px; height: 50px; }
.dashboard-hero h1 {
  font-size: 34px; font-weight: 800; margin: 0; letter-spacing: .02em;
  background: linear-gradient(135deg, #1677ff, #722ed1);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.dashboard-hero p { font-size: 15px; color: #8c8c8c; margin: 4px 0 0; }

/* 2x2 grid */
.module-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }

/* Card */
.module-card {
  position: relative; border-radius: 14px; cursor: pointer; overflow: hidden;
  transition: transform .2s, box-shadow .2s, border-color .2s;
  box-shadow: 0 2px 8px rgba(15, 23, 42, .06);
  display: flex; flex-direction: column;
  min-height: 164px; padding: 22px 24px 18px;
}
.module-card::before {
  content: ''; position: absolute; top: 18px; bottom: 18px; left: 0; width: 4px;
  border-radius: 0 4px 4px 0; background: var(--card-accent);
}
.module-card:hover { transform: translateY(-2px); box-shadow: 0 9px 22px rgba(15, 23, 42, .1); }
.module-card:active { transform: translateY(0); }
.module-card:focus-visible { outline: 3px solid rgba(22, 119, 255, .28); outline-offset: 3px; }

/* Top row: icon + heading side by side */
.card-top { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.card-icon {
  width: 44px; height: 44px; border-radius: 14px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.card-heading { flex: 1; min-width: 0; }
.card-heading h3 {
  margin: 0 0 4px; font-size: 19px; font-weight: 700; color: #1a1a1a;
  display: flex; align-items: center; gap: 8px; line-height: 1.3;
}
.card-heading p { margin: 0; font-size: 13px; color: #8c8c8c; line-height: 1.5; }
.card-entry {
  display: inline-flex; align-items: center; gap: 2px; flex-shrink: 0;
  padding-top: 2px; color: var(--card-accent); font-size: 12px; font-weight: 600;
  opacity: .58; transition: opacity .2s, transform .2s;
}
.module-card:hover .card-entry { opacity: 1; transform: translateX(2px); }

/* Tags */
.card-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.card-tag {
  padding: 4px 10px; border: 1px solid rgba(148,163,184,.16); border-radius: 6px;
  font-size: 13px; color: #667085;
  background: rgba(255,255,255,.82); box-shadow: 0 1px 2px rgba(15,23,42,.025);
  white-space: nowrap; flex-shrink: 0;
  transition: background .15s, border-color .15s, color .15s, transform .15s;
}
.card-tag:hover { background: #fff; color: #526071; }
.card-tag--link { color: #667085; cursor: pointer; }
.card-tag--link:hover { border-color: rgba(255,255,255,.95); color: var(--card-accent); transform: translateY(-1px); }
.card-tag--link:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }

/* ── Colors ── */
.module-api  { --card-accent: #1677ff; background: linear-gradient(135deg, #eff6ff, #dfedff); border: 1px solid rgba(22,119,255,.12); }
.module-api  .card-icon { background: linear-gradient(135deg,#1677ff,#69b1ff); color: #fff; }
.module-workbench { --card-accent: #13a8a8; background: linear-gradient(135deg, #f0fcf9, #ddf5ed); border: 1px solid rgba(19,194,194,.14); }
.module-workbench .card-icon { background: linear-gradient(135deg,#13c2c2,#5cdbd3); color: #fff; }
.module-tools { --card-accent: #d97812; background: linear-gradient(135deg, #fffaf3, #fff2df); border: 1px solid rgba(250,140,22,.14); }
.module-tools .card-icon { background: linear-gradient(135deg,#fa8c16,#ffc069); color: #fff; }
.module-nav   { --card-accent: #52a91d; background: linear-gradient(135deg, #f8fff2, #eaf8d9); border: 1px solid rgba(82,196,26,.14); }
.module-nav   .card-icon { background: linear-gradient(135deg,#52c41a,#95de64); color: #fff; }

/* ── Responsive ── */
@media (max-width: 768px) {
  .dashboard { max-width: none; padding: 0 16px; }
  .dashboard-hero { padding: 24px 0 20px; }
  .dashboard-hero h1 { font-size: 28px; }
  .dashboard-hero p { font-size: 14px; }
  .hero-logo { width: 40px; height: 40px; }
  .module-card { padding: 20px 20px 16px; }
  .card-icon { width: 40px; height: 40px; }
  .card-heading h3 { font-size: 17px; }
}
@media (max-width: 900px) {
  .module-grid { grid-template-columns: 1fr; gap: 16px; }
}
@media (max-width: 480px) {
  .dashboard-hero { padding: 18px 0 14px; }
  .dashboard-hero h1 { font-size: 24px; }
  .module-card { padding: 16px 16px 14px; }
  .card-icon { width: 38px; height: 38px; border-radius: 12px; }
  .card-heading h3 { font-size: 16px; }
  .card-entry span { display: none; }
}
</style>
