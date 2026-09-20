<template>
  <router-view v-slot="{ Component }">
    <KeepAlive include="ToolsLayout">
      <component :is="Component" />
    </KeepAlive>
  </router-view>
</template>

<script setup>
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: #f0f2f5;
  color: #303133;
  --nexus-primary: #1677ff;
  --nexus-border: #e8edf3;
  --nexus-border-hover: #cfd8e3;
  --nexus-shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.05);
  --nexus-shadow-md: 0 10px 26px rgba(15, 23, 42, 0.09);
  --nexus-shadow-focus: 0 0 0 3px rgba(22, 119, 255, 0.15);
  --nexus-ease: cubic-bezier(0.2, 0, 0, 1);
}

#app { width: 100%; height: 100vh; }

/* 按钮 */
.el-button { transition: transform 0.2s var(--nexus-ease), box-shadow 0.2s var(--nexus-ease), border-color 0.2s var(--nexus-ease), background-color 0.2s var(--nexus-ease), color 0.2s var(--nexus-ease) !important; font-size: 15px !important; font-weight: 500; }
.el-button:not(.is-disabled):hover { transform: translateY(-1px); }
.el-button:not(.is-disabled):active { transform: translateY(0); }
.el-button--primary:hover { box-shadow: 0 6px 16px rgba(22,119,255,0.28); }
.el-button--default:not(.is-disabled):hover { border-color: var(--nexus-primary); color: var(--nexus-primary); box-shadow: var(--nexus-shadow-sm); }
.el-button--small { font-size: 14px !important; }
.el-button--large { font-size: 17px !important; height: 44px; }
.el-button--default { font-size: 15px !important; }

/* 表格 */
.el-table { font-size: 16px; }
.el-table th.el-table__cell { background: #fafafa; font-weight: 600; color: #262626; font-size: 16px; padding: 13px 0; white-space: nowrap; }
.el-table td.el-table__cell { padding: 11px 0; }
.el-table .el-table__row { transition: background-color 0.18s var(--nexus-ease); }
.el-table .el-table__row:hover > td { background: #f0f7ff !important; }
.el-table .el-table__cell .cell { word-break: break-word; line-height: 1.5; }
.el-table td.el-table__cell.id-cell .cell { white-space: nowrap; }
.el-table td.el-table__cell.no-wrap .cell { white-space: nowrap; }

/* 主列表：页面不横向滚动，表格区域自己滚动 */
.ui-page .table-scroll,
.ui-page .table-wrap {
  min-width: 0;
  overflow-x: auto;
  overflow-y: auto;
}

.ui-page .table-scroll > .el-table,
.ui-page .table-wrap > .el-table {
  flex-shrink: 0;
}

.ui-page .el-table th.el-table__cell .cell {
  white-space: nowrap;
}

/* 表格操作列 */
.el-table td.el-table__cell .el-button + .el-button { margin-left: 8px; }

/* 表单 */
.el-form-item__label { font-size: 16px !important; font-weight: 500; }

/* 输入框 */
.el-input__wrapper { transition: box-shadow 0.2s var(--nexus-ease), border-color 0.2s var(--nexus-ease), background-color 0.2s var(--nexus-ease); }
.el-input__wrapper:hover { box-shadow: 0 0 0 1px var(--nexus-border-hover) inset; }
.el-input__wrapper.is-focus { box-shadow: var(--nexus-shadow-focus), 0 0 0 1px var(--nexus-primary) inset !important; }
.el-input__inner { font-size: 16px !important; }
.el-textarea__inner { font-size: 16px !important; line-height: 1.6; transition: box-shadow 0.2s var(--nexus-ease), border-color 0.2s var(--nexus-ease); }
.el-textarea__inner:focus { box-shadow: var(--nexus-shadow-focus); }

/* 标签 */
.el-tag { transition: transform 0.18s var(--nexus-ease), box-shadow 0.18s var(--nexus-ease), border-color 0.18s var(--nexus-ease); font-size: 14px !important; }
.el-tag:hover { transform: translateY(-1px); }

/* 树形控件 */
.el-tree { font-size: 16px; }
.el-tree-node__content { height: 38px; padding: 0 8px; }
.el-tree-node__label { font-size: 16px; }
.el-tree--highlight-current .el-tree-node.is-current > .el-tree-node__content { background: #e6f4ff !important; }
/* 移除所有树节点 hover/focus 效果 - 防抖和过渡 */
.el-tree .el-tree-node__content:hover,
.el-tree-node__content:hover {
  background-color: transparent !important;
  background: transparent !important;
  transition: none !important;
}
/* 阻止hover过渡动画导致的漂移 */
.el-tree-node__content {
  transition: none !important;
}

/* 对话框 */
.el-overlay-dialog {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  overflow: hidden;
}
.el-dialog {
  display: flex !important;
  flex-direction: column;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 48px);
  border-radius: 12px !important;
  overflow: hidden;
  margin: 0 !important;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.18) !important;
}
.el-dialog__header { flex-shrink: 0; border-bottom: 1px solid #f0f0f0; padding: 18px 24px; }
.el-dialog__title { font-size: 20px !important; font-weight: 600; }
.el-dialog__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 24px;
}
.el-dialog__footer {
  flex-shrink: 0;
  border-top: 1px solid #f0f0f0;
  padding: 14px 24px 16px;
}

/* 向导步骤：当前步骤和已完成步骤统一使用绿色，未开始步骤保持灰色。 */
.wizard-steps-green .el-step__head.is-process,
.wizard-steps-green .el-step__head.is-finish {
  color: #67c23a !important;
  border-color: #67c23a !important;
}
.wizard-steps-green .el-step__title.is-process,
.wizard-steps-green .el-step__title.is-finish,
.wizard-steps-green .el-step__description.is-process,
.wizard-steps-green .el-step__description.is-finish {
  color: #67c23a !important;
}
.wizard-steps-green .el-step__title.is-process,
.wizard-steps-green .el-step__title.is-finish {
  font-weight: 600;
}
.wizard-steps-green .el-step.is-process .el-step__main {
  margin: -6px -10px 0;
  padding: 6px 10px;
  border: 1px solid #e1f3d8;
  border-radius: 999px;
  background-color: #f0f9eb;
}
.wizard-steps-green .el-step__line-inner {
  border-color: #67c23a !important;
  background-color: #67c23a !important;
}
.wizard-steps-green .el-step__head.is-wait {
  color: #c0c4cc !important;
  border-color: #c0c4cc !important;
}
.wizard-steps-green .el-step__title.is-wait,
.wizard-steps-green .el-step__description.is-wait {
  color: #a8abb2 !important;
}
/* 顶层「配置 / 信息」页签紧接标题栏：页签本身自带上下留白，弹窗再给 24px 会把整个表单往下推 */
.el-dialog.case-edit-dialog > .el-dialog__body,
.el-dialog.iface-dialog > .el-dialog__body {
  padding-top: 8px;
}
.el-dialog.case-edit-dialog .el-dialog__body .el-form > .el-tabs > .el-tabs__header,
.el-dialog.iface-dialog .el-dialog__body .el-form > .el-tabs > .el-tabs__header {
  margin-bottom: 12px;
}

/* 抽屉 */
.el-drawer__header { border-bottom: 1px solid #f0f0f0; padding: 16px 24px; margin-bottom: 0; font-size: 18px; }

/* 面包屑 */
.el-breadcrumb { font-size: 16px; }
.el-breadcrumb__inner { font-weight: 500; transition: color 0.2s; }
.el-breadcrumb__inner.is-link {
  color: #1677ff;
  cursor: pointer;
  text-decoration: none;
}
.el-breadcrumb__inner.is-link:hover {
  color: #0958d9 !important;
  text-decoration: underline;
  text-underline-offset: 3px;
}

/* 下拉菜单 */
.el-dropdown-menu { border-radius: 10px !important; }
.el-dropdown-menu__item { font-size: 16px !important; padding: 10px 16px !important; transition: background-color 0.18s var(--nexus-ease), color 0.18s var(--nexus-ease); }

/* 分割线 */
.el-dialog .el-divider--horizontal, .el-drawer .el-divider--horizontal { margin: 20px 0; }
.el-dialog .el-form-item, .el-drawer .el-form-item { margin-bottom: 18px; }

/* 分页 */
.el-pagination { font-size: 16px; }
.el-pagination button, .el-pager li { font-size: 16px; }

/* 页面标题 */
.page-header h2 { font-size: 24px; font-weight: 700; }
.page-desc { font-size: 16px; }

/* 卡片 */
.el-card { transition: box-shadow 0.24s var(--nexus-ease), transform 0.24s var(--nexus-ease), border-color 0.24s var(--nexus-ease); border-radius: 12px; border-color: var(--nexus-border) !important; box-shadow: var(--nexus-shadow-sm); }
.el-card:hover { border-color: var(--nexus-border-hover) !important; box-shadow: var(--nexus-shadow-md) !important; transform: translateY(-2px); }
.el-card__header { padding: 16px 20px; }

/* 自绘卡片：项目、环境、参数集、树列表、统计、报告等保持同一套交互 */
/* 用明确类名替代 [class$="-card"] 属性子串匹配：属性子串选择器需对每个元素扫描 class 串，
   而类名选择器由浏览器按 class 分桶命中，能显著降低页面切换时的样式重算成本。以下清单为所有
   自身带 hover/过渡的卡片类，若后续新增卡片需要相同过渡，请在此追加类名。 */
.project-card,
.env-card,
.ps-card,
.module-card,
.tree-card,
.list-card,
.table-card,
.step-card,
.case-card,
.config-card,
.preview-card,
.result-card,
.workbench-stat-card {
  transition: transform 0.24s var(--nexus-ease), box-shadow 0.24s var(--nexus-ease), border-color 0.24s var(--nexus-ease), background-color 0.24s var(--nexus-ease);
}

.project-card:hover,
.env-card:hover,
.ps-card:hover,
.module-card:hover,
.tree-card:hover,
.list-card:hover,
.table-card:hover,
.step-card:hover,
.case-card:hover,
.config-card:hover,
.preview-card:hover,
.result-card:hover {
  border-color: var(--nexus-border-hover) !important;
  box-shadow: var(--nexus-shadow-md) !important;
  transform: translateY(-2px);
}

.project-card:active,
.env-card:active,
.ps-card:active,
.module-card:active {
  transform: translateY(0);
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
  }
}

/* 路由切换期间抑制过渡与动画：消除整页重建时的“过渡风暴”。
   仅在切换那一两帧生效（由 router 钩子添加/移除 .route-switching），不影响平时 hover 动效。 */
html.route-switching *,
html.route-switching *::before,
html.route-switching *::after {
  transition: none !important;
  animation: none !important;
}

/* 选择器 */
.el-select .el-input__inner { font-size: 16px !important; }
.interface-collection-cascader-popper { max-width: min(720px, calc(100vw - 48px)); }
.interface-collection-cascader-popper .el-cascader-panel { max-width: min(720px, calc(100vw - 48px)); overflow-x: auto; }
.interface-collection-cascader-popper .el-cascader-menu { min-width: 180px; max-height: 320px; }
.interface-collection-cascader-popper .el-cascader-menu__wrap { max-height: 320px; }
.interface-collection-cascader-popper .el-cascader-node { white-space: nowrap; }

/* 弹窗内表格字体 */
.el-dialog .el-table { font-size: 16px; }
.el-drawer .el-table { font-size: 16px; }

/* 滚动条 */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { background: #d9d9d9; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #bfbfbf; }
::-webkit-scrollbar-track { background: transparent; }
</style>
