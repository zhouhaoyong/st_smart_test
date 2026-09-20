<template>
  <el-dialog v-model="visible" :title="title" width="1080px" class="guide-dialog" destroy-on-close>
    <p class="guide-intro">{{ intro }}</p>

    <div class="guide-layout">
      <aside class="guide-menu" aria-label="使用指南目录">
        <span class="guide-menu__title">功能目录</span>
        <button
          v-for="section in sections"
          :key="section.key"
          type="button"
          class="guide-menu__item"
          :class="{ active: activeKey === section.key }"
          @click="activeKey = section.key"
        >
          {{ section.label }}
        </button>
      </aside>

      <section class="guide-content">
        <template v-if="activeSection">
          <div class="guide-heading">
            <span class="guide-heading__index">{{ activeSection.index }}</span>
            <div>
              <h3>{{ activeSection.label }}</h3>
              <p>{{ activeSection.summary }}</p>
            </div>
          </div>

          <div class="guide-block">
            <h4>如何使用</h4>
            <ol>
              <li v-for="step in activeSection.steps" :key="step">{{ step }}</li>
            </ol>
          </div>

          <div v-if="activeSection.flow?.length" class="guide-block">
            <h4>{{ activeSection.flowTitle || '状态与流转' }}</h4>
            <div class="guide-flow">
              <template v-for="(item, index) in activeSection.flow" :key="item">
                <el-tag size="small" effect="plain" :type="index === activeSection.flow.length - 1 ? 'success' : 'info'">{{ item }}</el-tag>
                <el-icon v-if="index < activeSection.flow.length - 1" color="#a8abb2"><ArrowRight /></el-icon>
              </template>
            </div>
            <p v-if="activeSection.flowDescription" class="guide-flow__description">{{ activeSection.flowDescription }}</p>
          </div>

          <el-alert v-if="activeSection.tip" :title="activeSection.tip" type="info" :closable="false" show-icon />
        </template>
      </section>
    </div>

    <template #footer>
      <el-button type="primary" @click="visible = false">我知道了</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '使用指南' },
  intro: { type: String, default: '' },
  sections: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})

const activeKey = ref(props.sections[0]?.key || '')
const activeSection = computed(() => props.sections.find(item => item.key === activeKey.value) || props.sections[0])

watch(() => props.sections, sections => {
  if (!sections.some(item => item.key === activeKey.value)) activeKey.value = sections[0]?.key || ''
})
</script>

<style scoped>
.guide-intro { margin: -4px 0 18px; color: #909399; font-size: 14px; line-height: 1.7; }
.guide-layout { display: flex; height: min(560px, calc(100vh - 270px)); min-height: 0; overflow: hidden; border: 1px solid #ebeef5; border-radius: 8px; }
.guide-menu { flex: 0 0 190px; padding: 14px 10px; overflow-y: auto; border-right: 1px solid #ebeef5; background: #fafcff; }
.guide-menu__title { display: block; padding: 4px 12px 10px; color: #909399; font-size: 13px; }
.guide-menu__item { display: block; width: 100%; padding: 10px 12px; border: 0; border-radius: 6px; background: transparent; color: #606266; font-size: 14px; text-align: left; cursor: pointer; }
.guide-menu__item:hover { background: #f0f7ff; color: #409eff; }
.guide-menu__item.active { background: #ecf5ff; color: #409eff; font-weight: 600; }
.guide-content { flex: 1; min-width: 0; min-height: 0; padding: 24px 28px; overflow-y: auto; }
.guide-heading { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 20px; }
.guide-heading__index { display: inline-flex; flex: 0 0 auto; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 8px; background: #409eff; color: #fff; font-size: 14px; font-weight: 600; }
.guide-heading h3 { margin: 1px 0 5px; color: #303133; font-size: 20px; }
.guide-heading p { margin: 0; color: #606266; font-size: 14px; line-height: 1.7; }
.guide-block { padding: 16px 18px; margin-bottom: 14px; border: 1px solid #ebeef5; border-radius: 8px; background: #fff; }
.guide-block h4 { margin: 0 0 10px; color: #303133; font-size: 15px; }
.guide-block ol { padding-left: 20px; margin: 0; color: #606266; font-size: 14px; line-height: 1.9; }
.guide-flow { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.guide-flow__description { margin: 12px 0 0; color: #606266; font-size: 13px; line-height: 1.7; }
@media (max-width: 760px) {
  .guide-layout { height: min(560px, calc(100vh - 250px)); flex-direction: column; }
  .guide-menu { display: flex; flex: 0 0 auto; gap: 6px; overflow-x: auto; overflow-y: hidden; border-right: 0; border-bottom: 1px solid #ebeef5; }
  .guide-menu__title { display: none; }
  .guide-menu__item { width: auto; white-space: nowrap; }
  .guide-content { padding: 20px; }
}
</style>
