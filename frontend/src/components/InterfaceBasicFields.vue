<template>
  <template v-if="$slots.status">
    <el-row :gutter="16">
      <el-col :span="14">
        <el-form-item label="接口名称" prop="name">
          <el-input v-model="form.name" placeholder="如：获取用户信息" maxlength="50" show-word-limit />
        </el-form-item>
      </el-col>
      <el-col :span="10">
        <el-form-item label="请求方法" prop="method">
          <el-select v-model="form.method" style="width: 100%">
            <el-option v-for="method in methods" :key="method" :label="method" :value="method" />
          </el-select>
        </el-form-item>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="14">
        <el-form-item label="URL" prop="url">
          <el-input v-model="form.url" placeholder="/api/v1/users" />
        </el-form-item>
      </el-col>
      <el-col :span="10">
        <slot name="service" />
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="14">
        <slot name="collection" />
      </el-col>
      <el-col :span="10">
        <slot name="description" />
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="14">
        <slot name="status" />
      </el-col>
      <el-col :span="10">
        <slot name="pending-reason" />
      </el-col>
    </el-row>
  </template>

  <template v-else>
    <el-row :gutter="16">
      <el-col :span="14">
        <el-form-item label="接口名称" prop="name">
          <el-input v-model="form.name" placeholder="如：获取用户信息" maxlength="50" show-word-limit />
        </el-form-item>
      </el-col>
      <el-col :span="10">
        <el-form-item label="请求方法" prop="method">
          <el-select v-model="form.method" style="width: 100%">
            <el-option v-for="method in methods" :key="method" :label="method" :value="method" />
          </el-select>
        </el-form-item>
      </el-col>
    </el-row>

    <el-form-item label="URL" prop="url">
      <el-input v-model="form.url" placeholder="/api/v1/users" />
    </el-form-item>
  </template>
</template>

<script setup>
defineProps({
  form: { type: Object, required: true },
  methods: { type: Array, default: () => [] },
})
</script>
