<template>
  <div class="record-metadata-table">
    <table>
      <tbody>
        <tr v-for="row in rows" :key="row.label">
          <th>{{ row.label }}</th>
          <td>
            <div v-if="row.person" class="metadata-person">
              <span class="metadata-avatar" :style="avatarStyle(row)">
                <img v-if="row.avatar" :src="row.avatar" :alt="`${row.label}头像`" />
                <span v-else>{{ avatarInitial(row.name) }}</span>
              </span>
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

function avatarInitial(name) {
  return (name || '?').trim().charAt(0) || '?'
}

const avatarColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']
const avatarStyle = (row) => ({ background: avatarColors[(row.userId || 0) % avatarColors.length] })
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

.metadata-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  flex: 0 0 24px;
  overflow: hidden;
  border-radius: 50%;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.metadata-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
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
