<template>
  <div class="record-metadata-table">
    <table>
      <tbody>
        <tr v-for="row in rows" :key="row.label">
          <th>{{ row.label }}</th>
          <td>
            <div v-if="row.person" class="metadata-person">
              <UserAvatar :size="24" :src="row.avatar" :name="row.name" :user-id="row.userId" :alt="`${row.label}头像`" />
              <span class="metadata-person-name">{{ row.name || '—' }}</span>
            </div>
            <span v-else>{{ row.value || '—' }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatBeijingTime } from '@/utils/beijingTime'
import UserAvatar from '@/components/UserAvatar.vue'

const props = defineProps({
  record: { type: Object, default: () => ({}) },
})

const rows = computed(() => {
  const record = props.record || {}
  const modifierName = record.updated_by_name || record.created_by_name
  const modifierAvatar = record.updated_by_avatar || record.created_by_avatar
  const modifierId = record.updated_by || record.created_by
  return [
    { label: 'ID', value: record.id },
    {
      label: '创建人',
      person: true,
      name: record.created_by_name,
      avatar: record.created_by_avatar,
      userId: record.created_by,
    },
    { label: '创建时间', value: formatTime(record.created_at) },
    {
      label: '修改人',
      person: true,
      name: modifierName,
      avatar: modifierAvatar,
      userId: modifierId,
    },
    { label: '修改时间', value: formatTime(record.updated_at || record.created_at) },
  ]
})

const formatTime = (value) => value ? formatBeijingTime(value) : ''

</script>

<style scoped>
.record-metadata-table {
  border: 1px solid #e8edf3;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

tr + tr {
  border-top: 1px solid #edf1f7;
}

th,
td {
  height: 46px;
  padding: 0 16px;
  text-align: left;
  font-size: 13px;
}

th {
  width: 140px;
  color: #606266;
  font-weight: 500;
  background: #f8fafc;
}

td {
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metadata-person {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
  vertical-align: middle;
}

.metadata-person-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 640px) {
  th,
  td {
    padding: 0 12px;
  }

  th {
    width: 100px;
  }
}
</style>
