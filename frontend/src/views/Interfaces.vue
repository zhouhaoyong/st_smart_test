<template>
  <div class="interfaces-container">
    <el-row :gutter="20" style="height: 100%">
      <!-- 左侧接口集目录树 -->
      <el-col :span="6">
        <div class="tree-card">
          <div class="tree-header">
            <h3>接口集</h3>
            <div class="tree-header-actions">
              <el-button size="small" @click="handleViewAll" :type="!activeCollection ? 'primary' : ''">全部接口</el-button>
              <el-button size="small" type="primary" @click="handleCreateRootCollection">新建根目录</el-button>
              <el-button size="small" type="danger" @click="openBatchDeleteDialog">批量删除</el-button>
            </div>
          </div>
          <el-tree
            class="collection-tree"
            :data="collectionTree"
            :props="treeProps"
            node-key="id"
            default-expand-all
            highlight-current
            draggable
            :allow-drop="allowDrop"
            @node-drop="handleTreeDrop"
            ref="treeRef"
          >
            <template #default="{ node, data }">
              <span
                class="custom-tree-node"
                @click.stop="handleNodeClick(data)"
                @dragover.prevent
                @drop.stop="handleInterfaceDrop(data)"
              >
                <span class="tree-node-label">
                  <CollectionNodeLabel :node="data" />
                </span>
                <span class="tree-node-actions">
                  <el-button link type="primary" size="small" @click.stop="handleCreateSubCollection(data)">
                    <el-icon><Plus /></el-icon>
                  </el-button>
                  <el-button link type="primary" size="small" @click.stop="handleEditCollection(data)">
                    <el-icon><Edit /></el-icon>
                  </el-button>
                  <el-button link type="danger" size="small" @click.stop="handleDeleteCollection(data)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </span>
              </span>
            </template>
            <template #empty><GlobalEmpty /></template>
          </el-tree>
        </div>
      </el-col>

      <!-- 右侧接口列表 -->
      <el-col :span="18">
        <div class="list-card">
          <div class="list-header">
            <h3>
              {{ activeCollection ? activeCollection.name + ' - 接口列表' : '全部接口' }}
            </h3>
          </div>
          <div class="list-toolbar-frame">
            <div class="interface-toolbar-row interface-filter-row">
              <el-form :inline="true" class="interface-filter-form" @submit.prevent="handleSearch">
                <el-form-item label="名称或 URL">
                  <el-input v-model="searchName" placeholder="搜索接口名称或 URL" clearable style="width:200px" @keyup.enter="handleSearch" />
                </el-form-item>
                <el-form-item label="方法">
                  <el-select v-model="searchMethod" clearable filterable placeholder="全部" style="width:100px">
                    <el-option v-for="method in interfaceMethodOptions" :key="method" :label="method" :value="method" />
                  </el-select>
                </el-form-item>
                <el-form-item label="接口状态">
                  <el-select v-model="searchWorkflowStatus" clearable placeholder="全部" style="width:110px">
                    <el-option label="待处理" value="pending" />
                    <el-option label="已处理" value="done" />
                  </el-select>
                </el-form-item>
                <el-form-item label="用例数">
                  <div class="case-count-filter">
                    <el-select v-model="searchCaseCountOperator" placeholder="条件" clearable style="width:112px" @clear="clearCaseCountFilter">
                      <el-option v-for="option in caseCountOperators" :key="option.value" :label="option.label" :value="option.value" />
                    </el-select>
                    <el-input-number
                      v-model="searchCaseCount"
                      min="0"
                      step="1"
                      controls-position="right"
                      placeholder="数量"
                      class="case-count-value-input"
                      style="width:92px"
                      @keyup.enter="handleSearch"
                    />
                  </div>
                </el-form-item>
                <el-form-item label="创建人">
                  <el-input v-model="searchCreator" placeholder="模糊搜索" clearable style="width:120px" @keyup.enter="handleSearch" />
                </el-form-item>
              </el-form>
            </div>
            <div class="interface-toolbar-row interface-actions-row">
              <div class="interface-primary-actions">
                <el-button type="primary" @click="handleSearch">查询</el-button>
                <el-button @click="resetSearch">重置</el-button>
                <el-button type="primary" @click="handleCreateInterface" :disabled="!activeCollection">新建接口</el-button>
                <el-dropdown trigger="click" @command="handleImportCommand">
                  <el-button>
                    导入<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="file">文件导入</el-dropdown-item>
                      <el-dropdown-item command="curl">cURL导入</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-button type="primary" @click="openInterfaceCaseGeneration">AI生成用例</el-button>
                <el-dropdown trigger="click" @command="handleBatchCommand">
                  <el-button type="primary">
                    批量操作{{ selectedIfaces.length ? ` (${selectedIfaces.length})` : '' }}<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="workflow" :disabled="!selectedIfaces.length">批量处理状态</el-dropdown-item>
                      <el-dropdown-item command="service" :disabled="!selectedIfaces.length">批量设置服务</el-dropdown-item>
                      <el-dropdown-item command="move" :disabled="!selectedIfaces.length">批量移动</el-dropdown-item>
                      <el-dropdown-item command="delete" :disabled="!selectedIfaces.length">批量删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-button @click="openImportLogDrawer">操作记录</el-button>
                <el-button @click="workflowGuideVisible = true">工作流指引</el-button>
              </div>
            </div>
          </div>

          <div class="interface-table-scroll" :class="{ 'is-empty': !interfaceList.length }" v-loading="loading">
            <el-table v-if="interfaceList.length" :data="interfaceList" height="100%" class="interface-table" stripe @row-dblclick="handleDebug" @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" fixed="left" />
            <el-table-column label="接口名称/URL" width="200" fixed="left">
              <template #default="{ row }">
                <div class="interface-name-url-cell">
                  <el-link class="interface-name-text" type="primary" draggable="true" @dragstart="handleInterfaceDragStart(row, $event)" @click="handleEdit(row)">{{ row.name || '-' }}</el-link>
                  <span class="interface-url-text">{{ row.url || '-' }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="用例数量" width="88" align="center">
              <template #default="{ row }">
                <el-link type="primary" underline="never" @click.stop="$router.push('/project/' + projectId + '/interfaces/' + row.id + '/cases')">
                  <CaseCountStatusBadge :count="row.test_case_count" :pending-count="row.pending_test_case_count" />
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="method" label="方法" width="84">
              <template #default="{ row }">
                <el-tag :type="getMethodType(row.method)" size="small">{{ row.method }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="服务标识" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ serviceName(row.service_key) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <button
                  type="button"
                  class="interface-status-trigger"
                  :title="`点击修改状态：${row.workflow_status_label || (row.workflow_status === 'done' ? '已处理' : '待处理')}`"
                  :aria-label="`修改接口状态：${row.workflow_status_label || (row.workflow_status === 'done' ? '已处理' : '待处理')}`"
                  @click.stop="openWorkflowStatusDialog(row)"
                >
                  <el-tag :type="row.workflow_status === 'done' ? 'success' : 'warning'" size="small">
                    {{ row.workflow_status_label || (row.workflow_status === 'done' ? '已处理' : '待处理') }}
                  </el-tag>
                </button>
              </template>
            </el-table-column>
            <el-table-column label="待处理原因" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ row.workflow_status === 'pending' ? (row.pending_reason_label || '-') : '-' }}</template>
            </el-table-column>
            <el-table-column prop="collection_name" label="所属接口集" min-width="130" show-overflow-tooltip />
            <el-table-column prop="created_by_name" label="创建人" width="96" show-overflow-tooltip />
            <el-table-column prop="created_at" label="创建时间" width="190">
              <template #default="{ row }">{{ formatBeijingTime(row.created_at) || '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <div class="interface-row-actions" @click.stop @dblclick.stop>
                  <el-dropdown trigger="click" @command="(command) => handleRowCommand(command, row)">
                    <el-button link type="primary" size="small">
                      更多<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="cases">用例管理</el-dropdown-item>
                        <el-dropdown-item command="edit">编辑</el-dropdown-item>
                        <el-dropdown-item command="copy" :disabled="copyingInterfaceId !== null">复制</el-dropdown-item>
                        <el-dropdown-item command="delete">删除</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </template>
            </el-table-column>
            </el-table>
            <GlobalEmpty v-else-if="!loading" />
          </div>

          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="total, sizes, prev, pager, next"
            :page-sizes="[10, 50, 100]"
            @current-change="onPageChange"
            @size-change="onPageSizeChange"
            style="margin-top:16px;justify-content:flex-end;display:flex"
          />
        </div>
      </el-col>
    </el-row>

    <!-- 接口集对话框 -->
    <el-dialog v-model="collectionDialogVisible" :title="collectionDialogTitle" width="min(500px, calc(100vw - 48px))">
      <el-form :model="collectionForm" :rules="collectionRules" ref="collectionFormRef" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="collectionForm.name" maxlength="20" show-word-limit placeholder="请输入接口集名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="collectionForm.description" type="textarea" :rows="2" placeholder="可选" maxlength="50" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="collectionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCollectionSubmit" :loading="collectionSubmitLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 批量删除接口集弹窗 -->
    <el-dialog v-model="batchDeleteDialogVisible" title="批量删除接口集" width="min(600px, calc(100vw - 48px))" destroy-on-close>
      <div style="margin-bottom:12px;display:flex;gap:12px;align-items:center">
        <el-button size="small" @click="toggleAllTreeNodes(true)">全选</el-button>
        <el-button size="small" @click="toggleAllTreeNodes(false)">取消全选</el-button>
        <span style="color:#909399;font-size:13px">已选 {{ checkedCollectionIds.length }} 个接口集</span>
      </div>
      <el-tree
        ref="batchDeleteTreeRef"
        :data="collectionTree"
        show-checkbox
        node-key="id"
        :props="treeProps"
        :default-expanded-keys="expandedCollectionIds"
        :check-strictly="true"
        @check="onBatchDeleteTreeCheck"
        style="max-height:400px;overflow:auto"
        :key="batchDeleteTreeKey"
      >
        <template #default="{ data }">
          <span style="font-weight:600;font-size:14px;display:flex;align-items:center;gap:6px">
            <CollectionNodeLabel :node="data" />
          </span>
        </template>
      </el-tree>
      <div style="margin-top:8px;color:#909399;font-size:12px;line-height:1.8">
        <el-icon style="vertical-align:middle"><InfoFilled /></el-icon>
        删除接口集将同时删除其下的所有接口、关联用例和执行项，此操作不可恢复。
      </div>
      <template #footer>
        <el-button @click="batchDeleteDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="confirmBatchDelete" :disabled="checkedCollectionIds.length === 0">删除 ({{ checkedCollectionIds.length }})</el-button>
      </template>
    </el-dialog>

    <!-- 接口编辑对话框 -->
    <InterfaceEditDialog
      v-model="interfaceDialogVisible"
      :model="interfaceForm"
      :title="interfaceDialogTitle"
      :collection-tree="collectionTree"
      :environment-services="environmentServices"
      :methods="methods"
      :saving="interfaceSubmitLoading"
      @save="handleInterfaceSubmit"
      @debug-interface="debugFromDialog"
      @manage-cases="openInterfaceCases"
    />

    <!-- 快速生成用例 -->
    <el-dialog v-model="genCaseVisible" title="生成用例" width="min(440px, calc(100vw - 48px))" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="用例名称" required>
          <el-input v-model="genCaseName" placeholder="如：登录成功验证" size="large" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="genCasePriority" style="width:100%" size="large">
            <el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="genCaseVisible = false">取消</el-button>
        <el-button type="primary" @click="submitGenCase" :loading="genCaseLoading">创建</el-button>
      </template>
    </el-dialog>

    <!-- 调试面板 -->
    <DebugPanel
      v-model="debugDialogVisible"
      title="接口调试"
      :method="debugMethod"
      :request-url="debugRequestUrl"
      :full-url="debugFullUrl"
      :req-headers="debugReqHeaders"
      :req-proxy="debugReqProxy"
      :req-service="debugReqService"
      :req-body="debugRequestBody"
      :req-params="debugReqParams"
      :req-path-params="debugReqPathParams"
      :loading="debugLoading"
      :response="debugResponse"
      :error="debugError"
      :status-code="debugStatusCode"
      :duration="debugDuration"
      :resp-headers="debugRespHeaders"
      :logs="debugLogs"
      @send="sendDebugRequest"
    />

    <el-dialog v-model="batchServiceDialogVisible" title="批量设置服务标识" width="min(420px, calc(100vw - 48px))">
      <el-form label-width="90px">
        <el-form-item label="服务标识">
          <el-select v-model="batchServiceKey" placeholder="不使用服务标识" clearable allow-create filterable style="width:100%">
            <el-option v-for="svc in environmentServices" :key="svc.key" :label="serviceOptionLabel(svc)" :value="svc.key" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchServiceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitBatchService">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchWorkflowDialogVisible" title="批量处理接口状态" width="min(460px, calc(100vw - 48px))" destroy-on-close>
      <div class="batch-workflow-copy">已选 {{ selectedIfaces.length }} 个接口。状态不会因勾选或生成用例自动变更，请选择本次要统一设置的状态。</div>
      <div class="batch-workflow-options">
        <el-button type="warning" plain @click="submitBatchWorkflow('pending')">标记为待处理</el-button>
        <el-button type="success" @click="submitBatchWorkflow('done')">标记为已处理</el-button>
      </div>
    </el-dialog>

    <el-dialog v-model="batchMoveDialogVisible" title="移动接口" width="min(600px, calc(100vw - 48px))" destroy-on-close>
      <div style="margin-bottom:12px;display:flex;gap:12px;align-items:center">
        <el-button size="small" @click="clearBatchMoveTarget" :disabled="!batchMoveTargetCollectionId">取消选择</el-button>
        <span style="color:#909399;font-size:13px">已选 {{ selectedIfaces.length }} 个接口</span>
        <span style="color:#909399;font-size:13px">目标 {{ batchMoveTargetName || '未选择' }}</span>
      </div>
      <CollectionSingleSelect
        v-model="batchMoveTargetCollectionId"
        :collection-tree="collectionTree"
        :disabled-ids="batchMoveDisabledCollectionIds"
        placeholder="请选择目标接口集"
      />
      <div style="margin-top:8px;color:#909399;font-size:12px;line-height:1.8">
        <el-icon style="vertical-align:middle"><InfoFilled /></el-icon>
        移动接口后，用例和执行项仍会关联原接口；请确认目标接口集是否正确。
      </div>
      <template #footer>
        <el-button @click="batchMoveDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          @click="submitBatchMove"
          :loading="batchMoveLoading"
          :disabled="!canSubmitBatchMove"
        >
          移动 ({{ selectedIfaces.filter(row => row.collection_id !== batchMoveTargetCollectionId).length }})
        </el-button>
      </template>
    </el-dialog>

    <!-- cURL 导入对话框 -->
    <el-dialog v-model="curlDialogVisible" title="cURL 导入" class="curl-import-dialog" :width="curlImportReport ? 'min(760px, calc(100vw - 48px))' : (curlBatchMode ? 'min(1000px, calc(100vw - 48px))' : 'min(600px, calc(100vw - 48px))')" destroy-on-close @closed="curlBatchMode = false; curlBatchResults = []; curlBatchErrors = []; curlBatchFilter = ''; curlImportReport = null">
      <div v-if="!curlBatchMode && !curlImportReport">
        <el-alert :title="curlImportNotice" type="warning" :closable="false" show-icon style="margin-bottom:12px" />
        <ImportTargetPicker
          v-model:mode="curlTargetMode"
          v-model:collection-id="curlTargetCollectionId"
          v-model:new-path="curlTargetNewPath"
          :collection-tree="collectionTree"
          :target-collection="activeCollection"
          required
          label-width="110px"
          class="curl-import-target"
        />
        <el-form label-width="110px">
          <el-form-item label="cURL 命令">
            <el-input v-model="curlText" type="textarea" :rows="6" placeholder="粘贴 cURL 命令，支持批量粘贴多条。" />
          </el-form-item>
        </el-form>
      </div>
      <div v-else-if="curlBatchMode && !curlImportReport">
        <el-alert :title="curlImportNotice" type="warning" :closable="false" show-icon style="margin-bottom:12px" />
        <ImportTargetPicker
          v-model:mode="curlTargetMode"
          v-model:collection-id="curlTargetCollectionId"
          v-model:new-path="curlTargetNewPath"
          :collection-tree="collectionTree"
          :target-collection="activeCollection"
          required
          label-width="110px"
          class="curl-import-target"
        />
        <div style="margin-bottom: 12px; display: flex; gap: 12px; align-items: center">
          <el-input v-model="curlBatchFilter" placeholder="搜索接口名称或URL" clearable style="width: 240px" />
          <el-select v-model="curlBatchMethodFilter" placeholder="请求方法" clearable style="width: 120px">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
            <el-option label="PATCH" value="PATCH" />
          </el-select>
          <el-button size="small" :disabled="!curlBatchSelected.length" @click="openCurlBatchServiceDialog">
            选择并设置服务 ({{ curlBatchSelected.length }})
          </el-button>
          <el-button v-if="curlBatchSelected.length" type="danger" size="small" @click="handleCurlBatchDelete">删除选中 ({{ curlBatchSelected.length }})</el-button>
        </div>
        <el-table :data="filteredCurlResults" max-height="400" @selection-change="(rows) => curlBatchSelected = rows.map(r => r.index)" :row-key="(row) => row.index">
          <el-table-column type="selection" width="45" />
          <el-table-column label="方法" width="70">
            <template #default="{ row }">
              <el-tag :type="getMethodType(row.method)" size="small">{{ row.method }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="url" label="URL" min-width="180" show-overflow-tooltip />
          <el-table-column label="服务" min-width="170">
            <template #default="{ row }">
              <el-select v-model="row.service_key" clearable allow-create filterable placeholder="不使用服务标识" size="small">
                <el-option v-for="svc in environmentServices" :key="svc.key" :label="serviceOptionLabel(svc)" :value="svc.key" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="showCurlDetail(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="handleCurlDeleteOne(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="curlBatchErrors.length" style="margin-top: 10px;">
          <el-alert v-for="(err, i) in curlBatchErrors" :key="i" :title="'第' + (err.index + 1) + '个接口: ' + err.error" type="error" :closable="false" style="margin-bottom: 4px;" />
        </div>
      </div>
      <div v-else-if="curlImportReport">
        <el-result :icon="curlImportReport.failed_count ? 'warning' : 'success'" :title="curlImportReport.failed_count ? 'cURL 批量导入完成，部分失败' : 'cURL 批量导入完成'">
          <template #sub-title>
            <ImportResultSummary :stats="curlImportStats">
              <div v-if="curlImportReport.skipped_interfaces">已跳过 {{ curlImportReport.skipped_interfaces }} 个重复接口（地址与请求结构完全相同）</div>
              <div v-if="curlImportReport.failed_count" class="curl-import-failure">失败：{{ curlImportReport.failed_count }} 项</div>
              <div v-if="curlImportReport.errors?.length" class="curl-import-failure-details">
                <div>失败详情</div>
                <p v-for="(err, i) in curlImportReport.errors" :key="i">{{ err }}</p>
              </div>
            </ImportResultSummary>
          </template>
          <template #extra>
            <el-button type="primary" @click="handleCurlImportDone">完成</el-button>
          </template>
        </el-result>
      </div>
      <template #footer>
        <template v-if="curlImportReport">
          <el-button @click="handleCurlImportDone">关闭</el-button>
        </template>
        <template v-else>
          <el-button @click="curlBatchMode ? (curlBatchMode = false) : (curlDialogVisible = false)">{{ curlBatchMode ? '返回' : '取消' }}</el-button>
        </template>
        <template v-if="curlBatchMode && !curlImportReport">
          <el-button type="primary" @click="handleCurlBatchImport(false)" :loading="curlBatchImporting === 'iface'" :disabled="!filteredCurlResults.length">
            导入接口 ({{ filteredCurlResults.length }})
          </el-button>
          <el-button type="primary" @click="handleCurlBatchImport(true)" :loading="curlBatchImporting === 'case'" :disabled="!filteredCurlResults.length">
            导入接口 + 生成用例 ({{ filteredCurlResults.length }})
          </el-button>
        </template>
        <el-button type="primary" @click="handleParseCurl" :loading="curlParsing" v-if="!curlBatchMode && !curlImportReport">解析 cURL</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="curlBatchServiceDialogVisible" title="批量设置服务" width="min(420px, calc(100vw - 48px))" append-to-body>
      <el-form label-width="80px">
        <el-form-item label="服务">
          <el-select v-model="curlBatchServiceKey" placeholder="不使用服务标识" clearable allow-create filterable style="width:100%">
            <el-option label="不使用服务标识" :value="null" />
            <el-option v-for="svc in environmentServices" :key="svc.key" :label="serviceOptionLabel(svc)" :value="svc.key" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="curlBatchServiceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="applyCurlBatchService">确定</el-button>
      </template>
    </el-dialog>

    <!-- cURL 接口编辑弹窗 -->
    <el-dialog v-model="curlDetailVisible" title="编辑接口" width="min(1000px, calc(100vw - 48px))" destroy-on-close>
      <template v-if="curlDetailItem">
        <el-form :model="curlDetailItem" label-width="100px">
          <InterfaceBasicFields :form="curlDetailItem" :methods="methods" />
          <RequestConfigTabs
            v-model:active-tab="curlDetailTab"
            :model="curlDetailItem"
            :body-rows="8"
            body-placeholder='{"key": "value"}'
            :param-show-type="false"
          />
        </el-form>
      </template>
      <template #footer>
        <el-button @click="curlDetailVisible = false">关闭</el-button>
        <el-button type="success" @click="handleCurlDetailDebug">调试</el-button>
      </template>
    </el-dialog>

    <!-- 导入对话框 -->
    <ImportDialog
      v-model="importDialogVisible"
      :project-id="projectId"
      :services="environmentServices"
      :target-collection="activeCollection"
      :collection-tree="collectionTree"
      @done="onImportDone"
      @result-ready="onImportResultReady"
      @debug-interface="handleImportDebug"
    />

    <BatchInterfaceCaseGenerationDialog
      v-model="interfaceCaseGenerationVisible"
      :project-id="projectId"
      :interfaces="selectedIfaces"
      :interface-ids="selectedIfaces.map(item => item.id)"
      :collection-tree="collectionTree"
      @done="onInterfaceCaseGenerationDone"
    />

    <InterfaceImportLogDrawer
      v-model="importLogDrawerVisible"
      :project-id="projectId"
    />

<InterfaceWorkflowStatusDialog
  v-model="workflowStatusDialogVisible"
  :status="workflowStatusDialog.status"
  :saving="workflowStatusSaving"
  @save="saveWorkflowStatus"
    />

    <el-dialog v-model="workflowGuideVisible" title="工作流指引" width="min(680px, calc(100vw - 48px))" destroy-on-close @closed="workflowGuideTab = 'workflow'">
      <el-tabs v-model="workflowGuideTab" class="workflow-guide-tabs">
        <el-tab-pane label="工作流指引" name="workflow">
          <div class="workflow-guide">
            <p class="workflow-guide-intro">按“接口导入 → 接口处理 → 用例确认 → 参数化 → 执行验证”完成 API 测试。</p>
            <div class="workflow-guide-status" aria-label="接口和用例状态流转">
              <div class="workflow-guide-status__row">
                <span class="workflow-guide-status__label">接口状态</span>
                <el-tag type="warning" size="small">待处理</el-tag>
                <span class="workflow-guide-status__arrow" aria-hidden="true">→</span>
                <el-tag type="success" size="small">已处理</el-tag>
              </div>
              <div class="workflow-guide-status__row">
                <span class="workflow-guide-status__label">用例状态</span>
                <el-tag type="warning" size="small">待确认</el-tag>
                <span class="workflow-guide-status__arrow" aria-hidden="true">→</span>
                <el-tag type="success" size="small">已确认</el-tag>
              </div>
            </div>
            <ol class="workflow-guide-list">
              <li>首次导入：通过<strong>文件导入</strong>选择<strong>全量模式</strong>。</li>
              <li>生成用例：人工确认范围后，在接口列表批量选择接口，点击<strong>AI生成用例</strong>。</li>
              <li>确认用例：检查参数、脚本和断言，确认无误后将用例设为 <el-tag type="success" size="small">已确认</el-tag>。</li>
              <li>配置参数化：多环境变化的值加入参数集，并在对应用例参数中设置引用。</li>
              <li>处理接口：接口下所有用例确认完成后，将接口设为 <el-tag type="success" size="small">已处理</el-tag>。</li>
              <li>版本迭代：通过<strong>文件导入</strong>选择<strong>增量模式</strong>；新增接口会被添加，变更接口同步更新，受影响接口进入 <el-tag type="warning" size="small">待处理</el-tag>，关联用例进入 <el-tag type="warning" size="small">待确认</el-tag>。</li>
              <li>复核变更：人工处理新接口、变更接口和待确认用例，完成检查与调整。</li>
              <li>执行验证：确认无误后，将用例加入执行集，用于后续常规测试。</li>
            </ol>
          </div>
        </el-tab-pane>
        <el-tab-pane label="状态说明" name="status">
          <div class="workflow-guide workflow-guide-legend" aria-label="接口、用例和优先级颜色说明">
            <p class="workflow-guide-intro">标签用于快速识别接口状态、用例状态和用例优先级。</p>
            <section class="workflow-guide-legend__section">
              <div class="workflow-guide-legend__title">接口状态</div>
              <div class="workflow-guide-legend__items">
                <div class="workflow-guide-legend__item">
                  <el-tag type="warning" size="small">待处理</el-tag>
                  <span>接口定义待检查，检查完成后手动标记为已处理。</span>
                </div>
                <div class="workflow-guide-legend__item">
                  <el-tag type="success" size="small">已处理</el-tag>
                  <span>接口定义已检查，可继续确认关联用例。</span>
                </div>
              </div>
            </section>
            <section class="workflow-guide-legend__section">
              <div class="workflow-guide-legend__title">用例状态</div>
              <div class="workflow-guide-legend__items">
                <div class="workflow-guide-legend__item">
                  <el-tag type="warning" size="small">待确认</el-tag>
                  <span>参数、脚本和断言待检查，完成后手动标记为已确认。</span>
                </div>
                <div class="workflow-guide-legend__item">
                  <el-tag type="success" size="small">已确认</el-tag>
                  <span>用例已确认，可加入执行集。</span>
                </div>
              </div>
            </section>
            <section class="workflow-guide-legend__section">
              <div class="workflow-guide-legend__title">用例优先级</div>
              <div class="workflow-guide-legend__priority-items">
                <span><el-tag type="danger" class="workflow-guide-priority-high" size="small">高</el-tag> 优先验证</span>
                <span><el-tag type="success" class="workflow-guide-priority-medium" size="small">中</el-tag> 按计划验证</span>
                <span><el-tag type="primary" class="workflow-guide-priority-low" size="small">低</el-tag> 可延后验证</span>
              </div>
            </section>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed, inject, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, InfoFilled, ArrowDown } from '@element-plus/icons-vue'
import { getCollectionTree, createCollection, updateCollection, deleteCollection, reorderCollections, batchDeleteCollections, previewDeleteCollection } from '@/api/collections'
import { getInterfaces, getInterface, getInterfaceMethods, createInterface, updateInterface, moveInterface, batchMoveInterfaces, deleteInterface, batchDeleteInterfaces, copyInterface, batchUpdateInterfaceService, batchUpdateInterfaceWorkflowStatus, batchImportCurl } from '@/api/interfaces'
import { createTestCase } from '@/api/testcases'
import { useUserStore } from '@/stores/user'
import DebugPanel from '@/components/DebugPanel.vue'
import CaseCountStatusBadge from '@/components/CaseCountStatusBadge.vue'
import InterfaceBasicFields from '@/components/InterfaceBasicFields.vue'
import RequestConfigTabs from '@/components/RequestConfigTabs.vue'
import InterfaceEditDialog from '@/components/InterfaceEditDialog.vue'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import ImportDialog from '@/components/ImportDialog.vue'
import BatchInterfaceCaseGenerationDialog from '@/components/BatchInterfaceCaseGenerationDialog.vue'
import InterfaceImportLogDrawer from '@/components/InterfaceImportLogDrawer.vue'
import InterfaceWorkflowStatusDialog from '@/components/InterfaceWorkflowStatusDialog.vue'
import ImportResultSummary from '@/components/ImportResultSummary.vue'
import ImportTargetPicker from '@/components/ImportTargetPicker.vue'
import CollectionNodeLabel from '@/components/CollectionNodeLabel.vue'
import CollectionSingleSelect from '@/components/CollectionSingleSelect.vue'
import { parseCurls } from '@/api/tools'
import { useInterfaceDebug } from '@/composables/useInterfaceDebug'
import { confirmDelete } from '@/utils/confirmDelete'
import {
  findCollectionPath,
  isImportTargetReady,
  removeCollectionAncestorsFromSelection,
  splitCollectionPathInput,
} from '@/utils/interfaceCollections'
import { formatServiceOptionLabel, getEnvironmentServices, getEnabledEnvironmentServices, matchServiceFromUrl } from '@/utils/serviceEnvironment'
import { formatBeijingTime } from '@/utils/beijingTime'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const projectId = computed(() => route.params.id)
const selectedEnvironment = inject('selectedEnvironment', computed(() => null))
const selectedParameterSet = inject('selectedParameterSet', computed(() => null))

// 接口集树
const collectionTree = ref([])
const activeCollection = ref(null)
const treeRef = ref(null)
const treeProps = { children: 'children', label: 'name' }

// 按项目记住上次选择的接口集，刷新后恢复原来的接口列表
const collectionMemoryKey = () => `interfaces_collection_${projectId.value}`
const readRememberedCollectionId = () => {
  try {
    const value = Number(localStorage.getItem(collectionMemoryKey()))
    return value > 0 ? value : null
  } catch { return null }
}
const rememberCollectionId = (collectionId) => {
  try {
    if (collectionId) localStorage.setItem(collectionMemoryKey(), String(collectionId))
    else localStorage.removeItem(collectionMemoryKey())
  } catch { /* 忽略本地存储不可用 */ }
}

const restoreRememberedCollection = async () => {
  const collectionId = readRememberedCollectionId()
  if (!collectionId) return null

  const path = findCollectionPath(collectionTree.value, collectionId)
  const collection = path[path.length - 1] || null
  if (!collection) {
    rememberCollectionId(null)
    return null
  }

  activeCollection.value = collection
  await nextTick()
  treeRef.value?.setCurrentKey(collection.id)
  return collection.id
}

// 接口列表
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const interfaceList = ref([])
const searchName = ref('')
const searchWorkflowStatus = ref('')
const searchCaseCountOperator = ref('')
const searchCaseCount = ref(null)
const searchMethod = ref('')
const searchCreator = ref('')
const caseCountOperators = [
  { label: '=', value: 'eq' },
  { label: '>', value: 'gt' },
  { label: '≧', value: 'gte' },
  { label: '<', value: 'lt' },
  { label: '≦', value: 'lte' },
  { label: '≠', value: 'ne' },
]
const methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
const interfaceMethodOptions = ref([...methods])

// 接口集对话框
const collectionDialogVisible = ref(false)
const collectionDialogTitle = ref('')
const collectionFormRef = ref(null)
const collectionSubmitLoading = ref(false)
const collectionForm = reactive({ id: null, name: '', description: '', parentId: null })
const collectionRules = { name: [{ required: true, message: '请输入名称', trigger: 'blur' }] }

// 接口对话框
const interfaceDialogVisible = ref(false)
const interfaceDialogTitle = ref('')
const interfaceSubmitLoading = ref(false)
const interfaceForm = reactive({
  id: null, name: '', method: 'GET', url: '', description: '',
  created_by: null, updated_by: null,
  created_by_name: '', created_by_avatar: '', updated_by_name: '', updated_by_avatar: '',
  created_at: null, updated_at: null,
  tags_text: '', headers: [], query_params: [], path_params: [], body_type: '', body_content: '',
  body_schema_types: {}, pre_script: '', post_script: '', collection_id: null, service_key: null,
  workflow_status: 'pending', workflow_status_label: '待处理', pending_reason: null, pending_reason_label: null,
})

const environmentServices = computed(() => getEnvironmentServices(selectedEnvironment.value))
const enabledEnvironmentServices = computed(() => getEnabledEnvironmentServices(selectedEnvironment.value))
const serviceOptionLabel = formatServiceOptionLabel
const serviceName = (key) => {
  if (!key) return '-'
  const svc = environmentServices.value.find(item => item.key === key)
  return svc ? `${svc.name || svc.key}` : key
}
// 调试：与用例管理页共用同一套调试状态与请求逻辑
const {
  debugDialogVisible,
  debugInterface,
  debugLoading,
  debugMethod,
  debugRequestUrl,
  debugFullUrl,
  debugReqHeaders,
  debugReqProxy,
  debugReqService,
  debugReqParams,
  debugReqPathParams,
  debugRequestBody,
  debugResponse,
  debugRespHeaders,
  debugError,
  debugStatusCode,
  debugDuration,
  debugLogs,
  ensureDebugEnvironment,
  resetDebugResult,
  sendDebugRequest,
} = useInterfaceDebug({ environment: selectedEnvironment, parameterSet: selectedParameterSet })

// 批量删除
const selectedIfaces = ref([])
const draggedInterface = ref(null)
const batchServiceDialogVisible = ref(false)
const batchServiceKey = ref(null)
const batchMoveDialogVisible = ref(false)
const batchMoveTargetCollectionId = ref(null)
const batchMoveLoading = ref(false)
const checkedCollectionIds = ref([])
const importDialogVisible = ref(false)
const workflowGuideVisible = ref(false)
const workflowGuideTab = ref('workflow')
const interfaceCaseGenerationVisible = ref(false)
const copyingInterfaceId = ref(null)
const batchWorkflowDialogVisible = ref(false)
const importLogDrawerVisible = ref(false)
const workflowStatusDialogVisible = ref(false)
const workflowStatusSaving = ref(false)
const workflowStatusDialog = reactive({ interfaceId: null, status: 'pending' })

// cURL 导入
const curlDialogVisible = ref(false)
// 导入目标在弹窗内选，不再要求先在左侧点中接口集
const curlTargetMode = ref('existing')
const curlTargetCollectionId = ref(null)
const curlTargetNewPath = ref('')
const curlTargetReady = computed(() => isImportTargetReady({
  mode: curlTargetMode.value,
  collectionId: curlTargetCollectionId.value,
  newPath: curlTargetNewPath.value,
}))
const curlText = ref('')
const curlParsing = ref(false)
const curlBatchMode = ref(false)
const curlBatchResults = ref([])
const curlBatchSelected = ref([])
const curlBatchErrors = ref([])
const curlBatchImporting = ref(false)
const curlBatchFilter = ref('')
const curlBatchMethodFilter = ref('')
const curlBatchServiceDialogVisible = ref(false)
const curlBatchServiceKey = ref(null)
const curlBatchRawItems = ref([])  // 未去重列表，用于创建不同参数的用例
const curlImportReport = ref(null)
const curlImportNotice = computed(() => {
  const countText = curlBatchMode.value
    ? `共解析 ${curlBatchResults.value.length} 个接口${curlBatchErrors.value.length ? `，${curlBatchErrors.value.length} 个接口失败` : ''}`
    : ''
  return [countText, '导入前请确认目标接口集，解析后可调整接口信息和服务标识。'].filter(Boolean).join('；')
})
const curlImportStats = computed(() => {
  const report = curlImportReport.value || {}
  return [
    { key: 'new_modules', label: '新增接口集', value: report.new_modules || 0, unit: '个' },
    { key: 'new_interfaces', label: '新增接口', value: report.new_interfaces ?? report.imported_interfaces ?? 0, unit: '个' },
    { key: 'updated_interfaces', label: '更新接口', value: report.updated_interfaces || 0, unit: '个' },
    { key: 'new_test_cases', label: '新增用例', value: report.new_test_cases ?? report.created_cases ?? 0, unit: '个' },
    { key: 'updated_test_cases', label: '更新用例', value: report.updated_test_cases || 0, unit: '个' },
  ]
})

// curl 编辑弹窗
const curlDetailVisible = ref(false)
const curlDetailItem = ref(null)
const curlDetailTab = ref('query')

const showCurlDetail = (row) => {
  if (!Array.isArray(row.path_params)) row.path_params = []
  curlDetailItem.value = row
  if (row.method === 'GET') { curlDetailTab.value = 'query' }
  else if (row.body_type || row.body_content) { curlDetailTab.value = 'body' }
  else { curlDetailTab.value = 'query' }
  curlDetailVisible.value = true
}

const filteredCurlResults = computed(() => {
  let list = curlBatchResults.value
  if (curlBatchFilter.value) {
    const kw = curlBatchFilter.value.toLowerCase()
    list = list.filter(r => r.name.toLowerCase().includes(kw) || r.url.toLowerCase().includes(kw))
  }
  if (curlBatchMethodFilter.value) {
    list = list.filter(r => r.method === curlBatchMethodFilter.value)
  }
  return list
})

// 批量删除弹窗
const batchDeleteDialogVisible = ref(false)
const batchDeleteTreeRef = ref(null)
const batchDeleteTreeKey = ref(0)
const getAllTreeKeys = (nodes) => {
  let keys = []
  for (const n of (nodes || [])) {
    keys.push(n.id)
    if (n.children) keys = keys.concat(getAllTreeKeys(n.children))
  }
  return keys
}

const allTreeKeys = computed(() => getAllTreeKeys(collectionTree.value))
const expandedCollectionIds = computed(() => allTreeKeys.value)

const toggleAllTreeNodes = (check) => {
  if (check) {
    batchDeleteTreeRef.value?.setCheckedKeys(allTreeKeys.value)
    checkedCollectionIds.value = [...allTreeKeys.value]
  } else {
    batchDeleteTreeRef.value?.setCheckedKeys([])
    checkedCollectionIds.value = []
  }
}

const onBatchDeleteTreeCheck = (node, { checkedKeys }) => {
  const nodeId = String(node.id)
  const isChecked = checkedKeys.some(key => String(key) === nodeId)
  const nextKeys = isChecked
    ? [...checkedKeys]
    : removeCollectionAncestorsFromSelection(collectionTree.value, node.id, checkedKeys)
  if (nextKeys.length !== checkedKeys.length) batchDeleteTreeRef.value?.setCheckedKeys(nextKeys)
  checkedCollectionIds.value = nextKeys
}

const openBatchDeleteDialog = () => {
  checkedCollectionIds.value = []
  batchDeleteTreeKey.value++
  nextTick(() => {
    batchDeleteDialogVisible.value = true
  })
}

const confirmBatchDelete = async () => {
  if (checkedCollectionIds.value.length === 0) return
  const count = checkedCollectionIds.value.length
  try {
    await ElMessageBox.confirm(
      `将批量删除 ${count} 个接口集及其下的接口、关联用例和执行项，此操作不可恢复，确认删除？`,
      '批量删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  try {
    const res = await batchDeleteCollections(checkedCollectionIds.value)
    // Toast由后端返回的message自动显示
    if (activeCollection.value && checkedCollectionIds.value.includes(activeCollection.value.id)) {
      activeCollection.value = null
      interfaceList.value = []
    }
    checkedCollectionIds.value = []
    batchDeleteDialogVisible.value = false
    loadTree()
    loadInterfaces(activeCollection.value?.id || null)
  } catch { /* 错误已在拦截器提示 */ }
}

const handleSelectionChange = (rows) => { selectedIfaces.value = rows }

const handleInterfaceDragStart = (row, event) => {
  draggedInterface.value = row
  event?.dataTransfer?.setData('text/plain', String(row.id))
  if (event?.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

const handleInterfaceDrop = async (collection) => {
  const iface = draggedInterface.value
  draggedInterface.value = null
  if (!iface || !collection?.id) return
  if (iface.collection_id === collection.id) {
    ElMessage.info('接口已在该接口集')
    return
  }
  try {
    await moveInterface(iface.id, collection.id)
    await loadTree()
    await loadInterfaces(activeCollection.value?.id || null)
  } catch {
    // handled by request interceptor
  }
}

const handleBatchDelete = async () => {
  if (!selectedIfaces.value.length) return
  const count = selectedIfaces.value.length
  const ok = await confirmDelete(
    `${count} 个接口（其关联的用例也会被同步删除，请谨慎操作）`,
    '批量删除'
  )
  if (!ok) return
  try {
    await batchDeleteInterfaces(selectedIfaces.value.map(r => r.id))
    selectedIfaces.value = []
    loadTree()
    loadInterfaces(activeCollection.value?.id || null)
  } catch { /* 错误已在拦截器提示 */ }
}

const openBatchServiceDialog = () => {
  if (!selectedIfaces.value.length) return
  batchServiceKey.value = null
  batchServiceDialogVisible.value = true
}

const submitBatchService = async () => {
  if (!selectedIfaces.value.length) return
  try {
    await batchUpdateInterfaceService(selectedIfaces.value.map(r => r.id), batchServiceKey.value)
    batchServiceDialogVisible.value = false
    selectedIfaces.value = []
    loadInterfaces(activeCollection.value?.id || null)
  } catch { /* 错误已在拦截器提示 */ }
}

const isSameCollectionForAllSelected = (collectionId) => {
  return selectedIfaces.value.length > 0 && selectedIfaces.value.every(row => row.collection_id === collectionId)
}

const canSubmitBatchMove = computed(() => {
  return selectedIfaces.value.length > 0
    && !!batchMoveTargetCollectionId.value
    && !isSameCollectionForAllSelected(batchMoveTargetCollectionId.value)
})

const findCollectionById = (nodes, id) => {
  for (const node of (nodes || [])) {
    if (node.id === id) return node
    const found = findCollectionById(node.children, id)
    if (found) return found
  }
  return null
}

const batchMoveTargetName = computed(() => {
  return findCollectionById(collectionTree.value, batchMoveTargetCollectionId.value)?.name || ''
})

const batchMoveDisabledCollectionIds = computed(() => {
  if (!selectedIfaces.value.length) return []
  const selectedCollectionIds = new Set(selectedIfaces.value.map(item => String(item.collection_id)))
  return selectedCollectionIds.size === 1 ? [...selectedCollectionIds] : []
})

const openBatchMoveDialog = () => {
  if (!selectedIfaces.value.length) return
  batchMoveTargetCollectionId.value = null
  batchMoveDialogVisible.value = true
}

const clearBatchMoveTarget = () => {
  batchMoveTargetCollectionId.value = null
}

const submitBatchMove = async () => {
  if (!canSubmitBatchMove.value) return
  batchMoveLoading.value = true
  try {
    const targetId = batchMoveTargetCollectionId.value
    const items = selectedIfaces.value.filter(row => row.collection_id !== targetId)
    const result = await batchMoveInterfaces(
      items.map(item => item.id),
      targetId,
      { skipSuccessToast: true },
    )
    const successCount = Number(result?.success_count || 0)
    const failedCount = Number(result?.failed_count || 0)
    if (failedCount) {
      const details = (result?.failed || [])
        .map(item => `接口 ${item.interface_id}：${item.message || '移动失败'}`)
        .join('\n')
      await ElMessageBox.alert(details || '部分接口移动失败，请刷新后重试', '批量移动完成', {
        type: 'warning',
        confirmButtonText: '知道了',
      })
    } else {
      ElMessage.success(`已移动 ${successCount} 个接口`)
    }
    batchMoveDialogVisible.value = false
    batchMoveTargetCollectionId.value = null
    selectedIfaces.value = []
    await loadTree()
    await loadInterfaces(activeCollection.value?.id || null)
  } catch {
    // handled by request interceptor
  } finally {
    batchMoveLoading.value = false
  }
}

const openImportDialog = () => {
  // 导入目标在弹窗第一步选，不再要求先在左侧点中接口集
  importDialogVisible.value = true
}

const onImportDone = () => {
  importDialogVisible.value = false
}

const onImportResultReady = () => {
  loadTree()
  loadInterfaces(activeCollection.value?.id || null)
}

// AI 用例生成统一在三步向导中完成范围选择、生成设置和结果处理。
const openInterfaceCaseGeneration = () => {
  if (!projectId.value) {
    ElMessage.warning('缺少项目信息')
    return
  }
  interfaceCaseGenerationVisible.value = true
}

const openBatchWorkflowDialog = () => {
  if (!selectedIfaces.value.length) return
  batchWorkflowDialogVisible.value = true
}

const openWorkflowStatusDialog = (row) => {
  if (!row?.id) return
  workflowStatusDialog.interfaceId = row.id
  workflowStatusDialog.status = row.workflow_status || 'pending'
  workflowStatusDialogVisible.value = true
}

const saveWorkflowStatus = async (workflowStatus) => {
  if (!workflowStatusDialog.interfaceId || workflowStatusSaving.value) return
  workflowStatusSaving.value = true
  try {
    await updateInterface(workflowStatusDialog.interfaceId, { workflow_status: workflowStatus })
    workflowStatusDialogVisible.value = false
    await Promise.all([
      loadTree(),
      loadInterfaces(activeCollection.value?.id || null),
    ])
  } catch {
    // 错误已由请求拦截器提示，保留弹窗便于重试
  } finally {
    workflowStatusSaving.value = false
  }
}

const submitBatchWorkflow = async (workflowStatus) => {
  if (!selectedIfaces.value.length) return
  try {
    await batchUpdateInterfaceWorkflowStatus(
      selectedIfaces.value.map(row => row.id),
      workflowStatus,
    )
    batchWorkflowDialogVisible.value = false
    selectedIfaces.value = []
    await loadTree()
    await loadInterfaces(activeCollection.value?.id || null)
  } catch {
    // 错误已由请求拦截器提示
  }
}

const onInterfaceCaseGenerationDone = () => {
  selectedIfaces.value = []
  loadTree()
  loadInterfaces(activeCollection.value?.id || null)
}

const openImportLogDrawer = () => {
  importLogDrawerVisible.value = true
}

// cURL 导入
const openCurlDialog = () => {
  // 左侧已选中接口集时默认带出来，用户仍可在弹窗里改
  curlTargetMode.value = 'existing'
  curlTargetCollectionId.value = activeCollection.value?.id || null
  curlTargetNewPath.value = ''
  curlText.value = ''
  curlBatchMode.value = false
  curlBatchResults.value = []
  curlBatchRawItems.value = []
  curlBatchErrors.value = []
  curlBatchSelected.value = []
  curlBatchFilter.value = ''
  curlBatchMethodFilter.value = ''
  curlBatchServiceKey.value = null
  curlBatchServiceDialogVisible.value = false
  curlDialogVisible.value = true
}

const handleImportCommand = (command) => {
  if (command === 'file') openImportDialog()
  if (command === 'curl') openCurlDialog()
}

const handleBatchCommand = (command) => {
  const handlers = {
    workflow: openBatchWorkflowDialog,
    service: openBatchServiceDialog,
    move: openBatchMoveDialog,
    delete: handleBatchDelete,
  }
  handlers[command]?.()
}

const handleParseCurl = async () => {
  const text = curlText.value.trim()
  if (!text) { ElMessage.warning('请输入 cURL 命令'); return }

  curlBatchMode.value = true
  curlParsing.value = true
  try {
    const res = await parseCurls(text)
    curlBatchResults.value = (res.interfaces || []).map((r, i) => ({
      ...r, ...matchServiceFromUrl(r.url, enabledEnvironmentServices.value, selectedEnvironment.value?.base_url), index: i
    }))
    curlBatchRawItems.value = (res.raw_items || []).map((r, i) => ({
      ...r, ...matchServiceFromUrl(r.url, enabledEnvironmentServices.value, selectedEnvironment.value?.base_url), index: i
    }))
    curlBatchErrors.value = res.errors || []
    if (!curlBatchResults.value.length && !curlBatchErrors.value.length) {
      ElMessage.warning('未解析到有效的 cURL 命令')
      curlBatchMode.value = false
    }
  } catch {
    // 错误已由请求拦截器按后端 message 提示
    curlBatchMode.value = false
  } finally { curlParsing.value = false }
}

const openCurlBatchServiceDialog = () => {
  if (!curlBatchSelected.value.length) {
    ElMessage.warning('请先选择接口')
    return
  }
  curlBatchServiceKey.value = null
  curlBatchServiceDialogVisible.value = true
}

const applyCurlBatchService = () => {
  if (!curlBatchSelected.value.length) {
    ElMessage.warning('请先选择接口')
    return
  }
  const ids = new Set(curlBatchSelected.value)
  curlBatchResults.value.forEach(item => {
    if (ids.has(item.index)) item.service_key = curlBatchServiceKey.value || null
  })
  curlBatchRawItems.value.forEach(item => {
    if (ids.has(item.index)) item.service_key = curlBatchServiceKey.value || null
  })
  curlBatchServiceDialogVisible.value = false
}

const handleCurlDetailDebug = () => {
  const item = curlDetailItem.value
  if (!item) return
  const env = ensureDebugEnvironment()
  if (!env) return
  debugInterface.value = {
    method: item.method,
    url: item.url,
    headers: item.headers || [],
    query_params: item.query_params || [],
    path_params: item.path_params || [],
    body_type: item.body_type || '',
    body_content: item.body_content || '',
    pre_script: item.pre_script || '',
    post_script: item.post_script || '',
    service_key: item.service_key || null,
  }
  resetDebugResult()
  debugDialogVisible.value = true
  nextTick(sendDebugRequest)
}

const handleImportDebug = (item) => {
  const env = ensureDebugEnvironment()
  if (!env) return
  debugInterface.value = {
    method: item.method,
    url: item.url,
    headers: item.headers || [],
    query_params: item.query_params || [],
    path_params: item.path_params || [],
    body_type: item.body_type || '',
    body_content: item.body_content || '',
    pre_script: item.pre_script || '',
    post_script: item.post_script || '',
  }
  resetDebugResult()
  debugDialogVisible.value = true
  nextTick(sendDebugRequest)
}

const handleCurlDeleteOne = (row) => {
  curlBatchResults.value = curlBatchResults.value.filter(r => r.index !== row.index)
}

const handleCurlBatchDelete = () => {
  const ids = new Set(curlBatchSelected.value)
  curlBatchResults.value = curlBatchResults.value.filter(r => !ids.has(r.index))
  curlBatchRawItems.value = curlBatchRawItems.value.filter(r => !ids.has(r.index))
  curlBatchSelected.value = []
}

const handleCurlBatchImport = async (withCases) => {
  if (!filteredCurlResults.value.length) { ElMessage.warning('没有可导入的接口'); return }
  if (!curlTargetReady.value) {
    ElMessage.warning('请先选择导入到哪个接口集')
    return
  }
  curlBatchImporting.value = withCases ? 'case' : 'iface'
  try {
    const importKey = item => `${item.method}::${item.service_key || ''}::${item.url}`
    const interfaces = filteredCurlResults.value.map(item => ({
      key: importKey(item),
      name: item.name,
      method: item.method,
      url: item.url,
      service_key: item.service_key || null,
      headers: (item.headers || []).map(h => ({ key: h.key, value: h.value, description: '', type: 'string', type_source: 'inferred' })),
      // 不写 required：命令行里只能看出「这次传了」，看不出「是否必须传」，硬编码成不必填会误导 AI 生成用例
      query_params: (item.query_params || []).map(q => ({ key: q.key, value: q.value, description: '', type: 'string', type_source: 'inferred' })),
      path_params: (item.path_params || []).map(p => ({ key: p.key, value: p.value, description: p.description || '', required: p.required !== false, type: p.type || 'string', type_source: p.type_source || 'manual' })),
      body_content: item.body_content || '',
      body_type: item.body_type || null,
    }))
    const cases = withCases
      ? curlBatchRawItems.value.map(raw => ({
          interface_key: importKey(raw),
          name: `${raw.name}_用例_${raw.index + 1}`,
          priority: 'high',
          param_overrides: {
            method: raw.method,
            url: raw.url,
            headers: (raw.headers || []).map(h => ({ key: h.key, value: h.value, description: '', type: 'string', type_source: 'inferred' })),
            query_params: (raw.query_params || []).map(q => ({ key: q.key, value: q.value, description: '', type: 'string', type_source: 'inferred' })),
            body_type: raw.body_type || null,
            body_content: raw.body_content || '',
            pre_script: raw.pre_script || '',
            post_script: raw.post_script || '',
          },
          assertions: [{ type: 'jsonpath', expression: '$.code', operator: 'eq', expected: '200', enabled: true }],
        }))
      : []
    const result = await batchImportCurl({
      project_id: Number(projectId.value),
      collection_id: curlTargetMode.value === 'new' ? null : curlTargetCollectionId.value,
      collection_path: curlTargetMode.value === 'new'
        ? splitCollectionPathInput(curlTargetNewPath.value)
        : [],
      interfaces,
      cases,
    }, { skipSuccessToast: true })
    const imported = result?.imported_interfaces || 0
    const createdCases = result?.created_cases || 0
    const importErrors = (result?.errors || []).map(err => `${err.name || '批量导入'}：${err.error || '导入失败'}`)
    curlImportReport.value = {
      new_modules: result?.new_modules || 0,
      new_interfaces: result?.new_interfaces ?? imported,
      updated_interfaces: result?.updated_interfaces || 0,
      skipped_interfaces: result?.skipped_interfaces || 0,
      new_test_cases: result?.new_test_cases ?? createdCases,
      updated_test_cases: result?.updated_test_cases || 0,
      imported_interfaces: imported,
      created_cases: createdCases,
      failed_count: result?.failed_count || importErrors.length,
      errors: importErrors,
      with_cases: withCases,
    }
    loadInterfaces(activeCollection.value?.id || null)
    loadTree()
  } finally { curlBatchImporting.value = false }
}

const handleCurlImportDone = () => {
  curlImportReport.value = null
  curlDialogVisible.value = false
}

// --- 工具函数 ---
const getMethodType = (m) => {
  const map = { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }
  return map[m] || ''
}

const resetInterfaceForm = () => {
  Object.assign(interfaceForm, {
    id: null, name: '', method: 'GET', url: '', description: '',
    created_by: null, updated_by: null,
    created_by_name: '', created_by_avatar: '', updated_by_name: '', updated_by_avatar: '',
    created_at: null, updated_at: null,
    tags_text: '', headers: [], query_params: [], path_params: [], body_type: '', body_content: '', body_schema_types: {},
    pre_script: '', post_script: '', collection_id: activeCollection.value?.id || null, service_key: null,
    workflow_status: 'pending', workflow_status_label: '待处理', pending_reason: null, pending_reason_label: null,
  })
}

// --- 接口集树 ---
const loadTree = async () => {
  try {
    collectionTree.value = await getCollectionTree(projectId.value) || []
    return true
  } catch (e) {
    collectionTree.value = []
    return false
  }
}

const allowDrop = (draggingNode, dropNode, type) => {
  // 不允许拖入自己内部
  return type !== 'inner' || dropNode.data.id !== draggingNode.data.id
}

const handleTreeDrop = async (draggingNode, dropNode, dropType) => {
  // el-tree 不会自动更新源数据，需手动同步
  const srcId = draggingNode.data.id
  const targetId = dropNode.data.id
  // 从树中移除拖拽节点
  const removeNode = (nodes, id) => {
    for (let i = 0; i < nodes.length; i++) {
      if (nodes[i].id === id) return nodes.splice(i, 1)[0]
      if (nodes[i].children) {
        const found = removeNode(nodes[i].children, id)
        if (found) return found
      }
    }
    return null
  }
  const node = removeNode(collectionTree.value, srcId)
  if (!node) return
  // 插入到目标位置
  const insertNode = (nodes, targetId, node, type) => {
    for (let i = 0; i < nodes.length; i++) {
      if (nodes[i].id === targetId) {
        if (type === 'inner') {
          nodes[i].children = nodes[i].children || []
          nodes[i].children.push(node)
        } else if (type === 'before') {
          nodes.splice(i, 0, node)
        } else {
          nodes.splice(i + 1, 0, node)
        }
        return true
      }
      if (nodes[i].children && insertNode(nodes[i].children, targetId, node, type)) return true
    }
    return false
  }
  if (!insertNode(collectionTree.value, targetId, node, dropType)) {
    collectionTree.value.push(node)
  }
  // 收集新顺序并保存
  const collectNodes = (nodes, parentId = null, result = []) => {
    nodes.forEach((n, i) => {
      result.push({ id: n.id, parent_id: parentId, sort_order: i })
      if (n.children && n.children.length) {
        collectNodes(n.children, n.id, result)
      }
    })
    return result
  }
  try {
    await reorderCollections(collectNodes(collectionTree.value))
    loadTree()
  } catch { /* ignore */ }
}

let pendingCollectionLoadFrame = null

const scheduleCollectionLoad = (collectionId) => {
  if (pendingCollectionLoadFrame !== null) {
    cancelAnimationFrame(pendingCollectionLoadFrame)
  }
  pendingCollectionLoadFrame = requestAnimationFrame(() => {
    pendingCollectionLoadFrame = null
    loadInterfaces(collectionId)
  })
}

const handleNodeClick = (data) => {
  activeCollection.value = data
  rememberCollectionId(data?.id)

  // 使用 setCurrentKey 确保树节点正确高亮（立即执行，无延迟）
  if (data && data.id && treeRef.value) {
    treeRef.value.setCurrentKey(data.id)
  }

  page.value = 1 // 重置页码
  scheduleCollectionLoad(data.id)
}

const handleViewAll = () => {
  activeCollection.value = null
  rememberCollectionId(null)
  if (treeRef.value) treeRef.value.setCurrentKey(null)
  page.value = 1 // 重置页码
  scheduleCollectionLoad(null)
}

const handleCreateRootCollection = () => {
  collectionForm.id = null
  collectionForm.name = ''
  collectionForm.description = ''
  collectionForm.parentId = null
  collectionDialogTitle.value = '新建接口集'
  collectionDialogVisible.value = true
}

const handleCreateSubCollection = (data) => {
  collectionForm.id = null
  collectionForm.name = ''
  collectionForm.description = ''
  collectionForm.parentId = data.id
  collectionDialogTitle.value = `在 "${data.name}" 下新建子目录`
  collectionDialogVisible.value = true
}

const handleEditCollection = (data) => {
  collectionForm.id = data.id
  collectionForm.name = data.name
  collectionForm.description = data.description || ''
  collectionForm.parentId = data.parent_id
  collectionDialogTitle.value = '编辑接口集'
  collectionDialogVisible.value = true
}

const handleDeleteCollection = async (data) => {
  // 先获取删除预览
  let preview = { interfaces_count: data.interface_count || 0, test_cases_count: 0, execution_items_count: 0 }
  try {
    const p = await previewDeleteCollection(data.id)
    if (p) preview = p
  } catch {
    // 预览接口已返回权限错误时直接结束，避免随后确认并再次触发删除请求。
    return
  }

  const parts = [`接口集「${data.name}」`]
  if (preview.interfaces_count) parts.push(`${preview.interfaces_count} 个接口`)
  if (preview.test_cases_count) parts.push(`${preview.test_cases_count} 个关联用例`)
  if (preview.execution_items_count) parts.push(`${preview.execution_items_count} 个执行项`)
  const msg = parts.length > 1
    ? `将删除 ${parts.join('、')}，此操作不可恢复，确认删除？`
    : `确认删除接口集「${data.name}」？`

  try {
    await ElMessageBox.confirm(msg, '删除确认', { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' })
  } catch { return }

  try {
    await deleteCollection(data.id)
    // Toast由后端返回的message自动显示
    // 如果删除的是当前选中的接口集，切换到全部接口
    if (activeCollection.value?.id === data.id) {
      activeCollection.value = null
      interfaceList.value = []
      total.value = 0
    }
    loadTree()
    loadInterfaces(activeCollection.value?.id || null)
  } catch { /* 错误已在拦截器提示 */ }
}

const handleCollectionSubmit = async () => {
  if (!collectionFormRef.value) return
  await collectionFormRef.value.validate(async (valid) => {
    if (!valid) return
    collectionSubmitLoading.value = true
    try {
      const data = {
        name: collectionForm.name,
        description: collectionForm.description || null,
        project_id: parseInt(projectId.value),
        parent_id: collectionForm.parentId || null,
      }
      if (collectionForm.id) {
        await updateCollection(collectionForm.id, { name: data.name, description: data.description })
      } else {
        await createCollection(data)
      }
      collectionDialogVisible.value = false
      loadTree()
    } catch {
      // 错误已在拦截器提示
    } finally {
      collectionSubmitLoading.value = false
    }
  })
}

// --- 接口 CRUD ---
const loadInterfaceMethods = async () => {
  if (!projectId.value) return
  try {
    const res = await getInterfaceMethods(projectId.value)
    const values = Array.isArray(res) ? res : (res?.items || [])
    const projectMethods = [...new Set(
      values
        .map(value => String(value || '').trim().toUpperCase())
        .filter(Boolean),
    )].sort()
    interfaceMethodOptions.value = projectMethods.length ? projectMethods : [...methods]
  } catch {
    interfaceMethodOptions.value = [...methods]
  }
}

const loadInterfaces = async (collectionId) => {
  loading.value = true
  try {
    const extra = {}
    if (searchName.value.trim()) extra.keyword = searchName.value.trim()
    if (searchCreator.value) extra.created_by_name = searchCreator.value
    if (searchWorkflowStatus.value) extra.workflow_status = searchWorkflowStatus.value
    if (searchMethod.value) extra.method = searchMethod.value
    const caseCountFilter = buildCaseCountFilter()
    if (caseCountFilter) Object.assign(extra, caseCountFilter)
    let res
    if (collectionId) {
      res = await getInterfaces(collectionId, null, page.value, pageSize.value, extra)
    } else {
      res = await getInterfaces(null, projectId.value, page.value, pageSize.value, extra)
    }
    interfaceList.value = res.items || res || []
    total.value = res.total || 0
  } catch (e) {
    interfaceList.value = []
  } finally {
    loading.value = false
  }
}

const buildCaseCountFilter = () => {
  const rawCount = String(searchCaseCount.value ?? '').trim()
  if (!searchCaseCountOperator.value || !rawCount) return null
  const count = Number(rawCount)
  if (!Number.isInteger(count) || count < 0) return null
  return {
    test_case_count_operator: searchCaseCountOperator.value,
    test_case_count: count,
  }
}

const clearCaseCountFilter = () => {
  searchCaseCount.value = null
}

const validateCaseCountFilter = () => {
  const hasOperator = Boolean(searchCaseCountOperator.value)
  const rawCount = String(searchCaseCount.value ?? '').trim()
  const hasCount = rawCount !== ''
  if (hasOperator !== hasCount) {
    ElMessage.warning('请同时选择用例数条件并输入数量')
    return false
  }
  if (hasCount) {
    const count = Number(rawCount)
    if (!Number.isInteger(count) || count < 0) {
      ElMessage.warning('用例数量必须是非负整数')
      return false
    }
  }
  return true
}

const handleSearch = () => {
  if (!validateCaseCountFilter()) return
  page.value = 1
  loadInterfaces(activeCollection.value?.id || null)
}

const resetSearch = () => {
  searchName.value = ''
  searchCreator.value = ''
  searchCaseCountOperator.value = ''
  searchCaseCount.value = null
  searchWorkflowStatus.value = ''
  searchMethod.value = ''
  page.value = 1
  loadInterfaces(activeCollection.value?.id || null)
}

const onPageChange = (val) => {
  page.value = val
  loadInterfaces(activeCollection.value?.id || null)
}

const onPageSizeChange = (size) => {
  pageSize.value = size
  page.value = 1
  loadInterfaces(activeCollection.value?.id || null)
}


const handleCreateInterface = () => {
  resetInterfaceForm()
  interfaceDialogTitle.value = '新建接口'
  interfaceDialogVisible.value = true
}

const handleEdit = async (row) => {
  let detail
  try {
    detail = await getInterface(row.id)
  } catch {
    return
  }
  if (!detail) return
  const source = detail
  Object.assign(interfaceForm, {
    id: source.id, name: source.name, method: source.method, url: source.url,
    description: source.description || '',
    created_by: source.created_by, updated_by: source.updated_by,
    created_by_name: source.created_by_name || '', created_by_avatar: source.created_by_avatar || '',
    updated_by_name: source.updated_by_name || '', updated_by_avatar: source.updated_by_avatar || '',
    created_at: source.created_at, updated_at: source.updated_at,
    tags_text: (source.tags || []).join(', '),
    headers: (source.headers || []).map(h => typeof h === 'string' ? { key: h, value: '', type: 'string', type_source: 'manual' } : { type: 'string', type_source: 'manual', ...h }),
    query_params: (source.query_params || []).map(q => typeof q === 'string' ? { key: q, value: '', description: '', type: 'string', type_source: 'manual' } : { type: 'string', type_source: 'manual', ...q }),
    path_params: (source.path_params || []).map(p => typeof p === 'string' ? { key: p, value: '', required: true, description: '', type: 'string', type_source: 'manual' } : { type: 'string', type_source: 'manual', ...p }),
    body_type: source.body_type || '', body_content: source.body_content || '',
    body_schema_types: { ...(source.body_schema_types || {}) },
    pre_script: source.pre_script || '', post_script: source.post_script || '',
    collection_id: source.collection_id,
    service_key: source.service_key || null,
    workflow_status: source.workflow_status || 'pending',
    workflow_status_label: source.workflow_status_label || '待处理',
    pending_reason: source.pending_reason || null,
    pending_reason_label: source.pending_reason_label || null,
  })
  interfaceDialogTitle.value = '编辑接口'
  interfaceDialogVisible.value = true
}

const openInterfaceCases = (iface) => {
  if (!iface?.id) return
  router.push(`/project/${projectId.value}/interfaces/${iface.id}/cases`)
}

const handleCopy = async (row) => {
  if (copyingInterfaceId.value !== null) return
  copyingInterfaceId.value = row.id
  try {
    await copyInterface(row.id)
    await Promise.all([
      loadTree(),
      loadInterfaces(activeCollection.value?.id || null),
    ])
  } catch { /* 错误已在拦截器提示 */ }
  finally {
    copyingInterfaceId.value = null
  }
}

const handleRowCommand = (command, row) => {
  if (command === 'cases') {
    router.push('/project/' + projectId.value + '/interfaces/' + row.id + '/cases')
  } else if (command === 'edit') {
    handleEdit(row)
  } else if (command === 'copy') {
    handleCopy(row)
  } else if (command === 'delete') {
    handleDelete(row)
  }
}

const handleDelete = async (row) => {
  const ok = await confirmDelete(row.name, '接口')
  if (!ok) return
  await deleteInterface(row.id)
  // Toast由后端返回的message自动显示
  loadTree()
  loadInterfaces(activeCollection.value?.id || null)
}

const handleInterfaceSubmit = async (submittedData) => {
  if (!submittedData) return
  interfaceSubmitLoading.value = true
  try {
    const { id, ...data } = submittedData
    if (id) {
      await updateInterface(id, data)
    } else {
      await createInterface(data)
    }
    interfaceDialogVisible.value = false
    loadInterfaces(activeCollection.value?.id || null)
    loadTree()
  } catch {
    // 错误已在拦截器提示
  } finally {
    interfaceSubmitLoading.value = false
  }
}

// --- 参数表格操作 ---
const addHeader = () => interfaceForm.headers.push({ key: '', value: '', description: '', type: 'string', type_source: 'manual' })
const addQueryParam = () => interfaceForm.query_params.push({ key: '', value: '', description: '', type: 'string', type_source: 'manual' })

// --- 调试 ---
// 生成用例
const genCaseVisible = ref(false)
const genCaseName = ref('')
const genCasePriority = ref('high')
const genCaseLoading = ref(false)
const genCaseInterface = ref(null)

const handleGenCase = (row) => {
  genCaseInterface.value = row
  genCaseName.value = row.name + ' - 用例'
  genCasePriority.value = 'high'
  genCaseLoading.value = false
  genCaseVisible.value = true
}

const submitGenCase = async () => {
  if (!genCaseName.value.trim()) { ElMessage.warning('请输入用例名称'); return }
  const intf = genCaseInterface.value
  genCaseLoading.value = true
  try {
    await createTestCase({
      project_id: parseInt(projectId.value),
      interface_id: intf.id,
      name: genCaseName.value,
      priority: genCasePriority.value,
      owner: userStore.userInfo?.real_name || '',
      steps: [{
        name: intf.name, step_order: 1, interface_id: intf.id,
        param_overrides: {
          headers: (intf.headers || []).map(h => typeof h === 'string' ? { key: h, value: '' } : { ...h }),
          query_params: (intf.query_params || []).map(q => typeof q === 'string' ? { key: q, value: '' } : { ...q }),
          body_content: intf.body_content || '',
          body_schema_types: intf.body_schema_types || {},
        },
        script: null, assertions: [{type: "jsonpath", expression: "$.code", operator: "eq", expected: "200", enabled: true}],
      }],
    })
    genCaseVisible.value = false
  } catch { /* handled */ }
  finally { genCaseLoading.value = false }
}

const debugFromDialog = (iface = {}) => {
  if (!ensureDebugEnvironment()) return
  debugInterface.value = {
    id: iface.id,
    method: iface.method,
    url: iface.url,
    headers: iface.headers,
    query_params: iface.query_params,
    path_params: iface.path_params,
    body_type: iface.body_type,
    body_content: iface.body_content,
    pre_script: iface.pre_script,
    post_script: iface.post_script,
  }
  debugDialogVisible.value = true
  debugReqPathParams.value = iface.path_params || []
  sendDebugRequest()
}

const handleDebug = (row, column, event) => {
  if (column?.type === 'selection' || event?.target?.closest('td.el-table-column--selection')) return
  if (!ensureDebugEnvironment()) return
  debugInterface.value = row
  debugMethod.value = row.method || 'GET'
  debugRequestUrl.value = row.url || ''
  debugFullUrl.value = ''
  debugReqPathParams.value = row.path_params || []
  resetDebugResult()
  debugDialogVisible.value = true
}

const applyWorkflowStatusFromRoute = () => {
  const rawStatus = Array.isArray(route.query.workflow_status)
    ? route.query.workflow_status[0]
    : route.query.workflow_status
  const requestedStatus = ['pending', 'done'].includes(rawStatus) ? rawStatus : ''
  searchWorkflowStatus.value = requestedStatus
}

onMounted(async () => {
  if (projectId.value) {
    applyWorkflowStatusFromRoute()
    const treeLoaded = await loadTree()
    const rememberedCollectionId = treeLoaded ? await restoreRememberedCollection() : null
    await loadInterfaceMethods()
    await loadInterfaces(rememberedCollectionId)
  }
  // 从参数化页面跳转过来时自动打开对应接口
  const editId = route.query.edit
  if (editId) {
    const row = interfaceList.value.find(r => r.id === parseInt(editId))
    if (row) { handleEdit(row); router.replace({ query: {} }) }
  }
})
</script>

<style scoped>
.interfaces-container { height: 100%; min-width: 0; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.interfaces-container :deep(.el-row), .interfaces-container :deep(.el-col) { min-width: 0; min-height: 0; }
.interfaces-container :deep(.el-row) { flex: 1; }
.interfaces-container :deep(.el-col) { display: flex; flex-direction: column; height: 100%; }
.interfaces-container :deep(.el-col > .tree-card),
.interfaces-container :deep(.el-col > .list-card) { width: 100%; }

.tree-card, .list-card {
  background: #fff; border: 1px solid #f0f0f0; border-radius: 10px;
  padding: 18px; height: 100%; min-height: 0; display: flex; flex-direction: column;
}
.tree-card { overflow: hidden; }
.list-card { overflow: hidden; }

.tree-header, .list-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px; flex-wrap: wrap; gap: 8px; flex-shrink: 0;
}
.tree-header h3, .list-header h3 { margin: 0; font-size: 20px; font-weight: 600; color: #1a1a1a; }
.case-count-filter {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* 统一操作列背景色 */
:deep(.el-table__fixed-right) {
  box-shadow: none !important;
}
:deep(.el-table__fixed-right-patch) {
  background: transparent !important;
}
:deep(.el-table__fixed-right .el-table__row) {
  background: inherit !important;
}
:deep(.el-table__fixed-right .el-table__row:hover) {
  background: inherit !important;
}
.tree-header-actions { display: flex; gap: 4px; }
.tree-header .el-button { font-size: 14px; }
.collection-tree {
  flex: 1; min-width: 0; min-height: 0; overflow-y: auto;
}
.collection-tree {
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: #aeb8c4 #f7f9fc;
}
.collection-tree :deep(.el-tree-node__content) {
  width: 100%;
  min-width: 0;
  height: auto;
  min-height: 38px;
}
.collection-tree :deep(.el-tree-node__expand-icon) {
  flex-shrink: 0;
}
.collection-tree :deep(.el-tree__empty-block) {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.collection-tree :deep(.el-tree__empty-text) { width: 100%; }

/* 移除树节点 hover/focus 效果 - 彻底覆盖所有可能状态 */
:deep(.el-tree-node__content:hover),
:deep(.el-tree-node__content:focus),
:deep(.el-tree-node__content:focus-visible),
:deep(.el-tree-node__content:focus-within),
:deep(.el-tree .el-tree-node__content:hover),
:deep(.el-tree-node:hover > .el-tree-node__content),
:deep(.el-tree-node.is-focusable > .el-tree-node__content:hover),
:deep(.el-tree-node.is-focusable > .el-tree-node__content:focus),
:deep(.el-tree-node.is-focusable > .el-tree-node__content:focus-visible),
:deep(.el-tree-node.is-expanded > .el-tree-node__content:hover),
:deep(.el-tree-node.is-expanded > .el-tree-node__content:focus) {
  background-color: transparent !important;
  background: transparent !important;
  transition: none !important;
  outline: none !important;
}
/* 禁用树节点的焦点环 */
:deep(.el-tree-node__content:focus-visible) {
  outline: none !important;
  box-shadow: none !important;
}
/* 保留选中节点的高亮背景（highlight-current） */
:deep(.el-tree-node.is-current > .el-tree-node__content) {
  background-color: #e6f4ff !important;
}
/* 选中节点在鼠标停留或获得焦点时也必须保持高亮，避免被 hover 样式覆盖 */
:deep(.el-tree-node.is-current > .el-tree-node__content:hover),
:deep(.el-tree-node.is-current > .el-tree-node__content:focus),
:deep(.el-tree-node.is-current > .el-tree-node__content:focus-visible),
:deep(.el-tree-node.is-current > .el-tree-node__content:focus-within) {
  background-color: #e6f4ff !important;
  background: #e6f4ff !important;
}

.custom-tree-node {
  flex: 1; min-width: 0; display: flex; align-items: center; justify-content: space-between;
  gap: 8px; font-size: 15px; padding-right: 4px; height: 34px;
  overflow: hidden;
}
.tree-node-label {
  min-width: 0; flex: 1; display: flex; align-items: center; gap: 8px; overflow: hidden;
}
.custom-tree-node .el-icon { font-size: 17px; }
.tree-node-label .el-icon { flex-shrink: 0; }
.tree-node-text {
  min-width: 0; display: inline-flex; align-items: center; gap: 4px;
  overflow: hidden; white-space: nowrap;
}
.tree-node-name {
  min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tree-node-actions {
  width: 86px; flex: 0 0 86px; display: flex; justify-content: flex-end; gap: 2px;
}
.tree-node-actions .el-button {
  margin-left: 0;
}
.interface-count { color: #909399; font-size: 14px; flex-shrink: 0; }
/* 左侧树形区域支持滚动 */
.tree-with-checkbox {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.empty-hint {
  text-align: center; color: #909399; padding: 60px 0;
  font-size: 14px;
}

/* 右侧表格支持滚动，分页固定在卡片底部 */
.list-toolbar-frame {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  flex-shrink: 0;
}
.interface-toolbar-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  width: 100%;
  min-width: 0;
}
.interface-filter-row {
  flex-wrap: nowrap;
  overflow-x: auto;
  scrollbar-width: none;
}
.interface-filter-row::-webkit-scrollbar { display: none; }
.interface-actions-row {
  padding-top: 10px;
  border-top: 1px solid #edf1f6;
}
.interface-filter-form {
  display: flex !important;
  flex: 0 0 auto;
  align-items: flex-end;
  flex-wrap: nowrap;
  gap: 8px 12px;
  min-width: max-content;
  width: max-content;
  margin: 0 !important;
}
.interface-filter-form :deep(.el-form-item) {
  margin: 0 !important;
  flex: 0 0 auto;
}
.interface-filter-form :deep(.el-form-item__label) { padding-right: 8px; }
.interface-primary-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  flex: 1 1 auto;
  min-width: 0;
}
.interface-primary-actions .el-button,
.interface-primary-actions .el-dropdown {
  margin-left: 0 !important;
}
.interface-primary-actions > .el-button,
.interface-primary-actions > .el-dropdown,
.interface-primary-actions > .el-dropdown :deep(.el-button) {
  height: 32px;
  min-height: 32px;
  box-sizing: border-box;
}
.interface-primary-actions :deep(.el-dropdown) { display: inline-flex; }
.interface-table-scroll {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: auto;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: #aeb8c4 #f7f9fc;
}
.interface-table-scroll.is-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.interface-table-scroll.is-empty > :deep(.global-empty) { width: 100%; }
.interface-table-scroll :deep(.el-table) { width: 100%; min-width: 0; }
.interface-table-scroll :deep(.el-table__header .cell),
.interface-table-scroll :deep(.el-table__body .cell) {
  white-space: nowrap;
}
.interface-table-scroll :deep(.el-table__body .cell) {
  overflow: hidden;
  text-overflow: ellipsis;
}
.interface-table-scroll :deep(.interface-name-url-cell) {
  display: block;
  width: 100%;
  box-sizing: border-box;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  line-height: 1.45;
}
.interface-table-scroll :deep(.interface-name-text) {
  display: inline-flex;
  min-width: 0;
  width: auto;
  box-sizing: border-box;
  justify-content: flex-start;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}
.interface-table-scroll :deep(.interface-url-text) {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.interface-table-scroll :deep(.interface-name-text) { font-weight: 500; }
.interface-table-scroll :deep(.interface-url-text) {
  margin-top: 2px;
  color: #909399;
  font-size: 12px;
}
.interface-status-trigger {
  display: inline-flex;
  align-items: center;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}
.interface-status-trigger:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
  border-radius: 4px;
}
.interface-row-actions {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
.list-card :deep(.el-pagination) { flex-shrink: 0; }
.collection-tree::-webkit-scrollbar,
.interface-table-scroll::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.collection-tree::-webkit-scrollbar-track,
.interface-table-scroll::-webkit-scrollbar-track {
  background: #f7f9fc;
  border-radius: 4px;
}
.collection-tree::-webkit-scrollbar-thumb,
.interface-table-scroll::-webkit-scrollbar-thumb {
  background: #aeb8c4;
  border: 2px solid #f7f9fc;
  border-radius: 4px;
}
.collection-tree::-webkit-scrollbar-thumb:hover,
.interface-table-scroll::-webkit-scrollbar-thumb:hover {
  background: #8996a5;
}
@media (min-width: 1366px) and (max-width: 1600px) {
  .list-card { padding: 16px; }
  .interface-toolbar-row { gap: 6px 10px; }
  .interface-filter-form { gap: 6px 10px; }
  .interface-filter-form :deep(.el-form-item__label) { padding-right: 6px; }
}

.debug-url-bar {
  display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
  padding: 12px; background: #f5f7fa; border-radius: 6px;
}
.debug-url-bar .debug-url { flex: 1; font-size: 14px; font-family: monospace; color: #303133; }
.debug-error { margin-bottom: 12px; }
.curl-import-target { margin-bottom: 14px; }
.curl-import-dialog :deep(.el-result__subtitle) { width: 100%; }
.curl-import-failure { color: #e6a23c; }
.curl-import-failure-details { margin-top: 8px; max-height: 180px; overflow: auto; }
.curl-import-failure-details p { margin: 0 0 4px; color: #606266; }

.code-editor :deep(textarea) {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
}
.header-mode-bar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}
.body-editor {
  border: 1px solid #e8edf3;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}
.body-toolbar {
  min-height: 42px;
  padding: 6px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  background: #fbfcfe;
  border-bottom: 1px solid #edf1f7;
}
.body-toolbar-title {
  color: #303133;
  font-weight: 600;
  font-size: 13px;
}
.body-editor :deep(.el-textarea__inner) {
  border: 0;
  border-radius: 0;
  box-shadow: none;
  background: #fbfcfe;
}
.body-empty {
  height: 150px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 13px;
  background: #fafcff;
}
.json-error-text {
  padding: 6px 10px;
  color: #f56c6c;
  font-size: 12px;
  border-top: 1px solid #fef0f0;
  background: #fff7f7;
}
.batch-workflow-copy { color: #606266; line-height: 1.7; }
.batch-workflow-options { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.workflow-guide { color: #303133; }
.workflow-guide-intro { margin: 0 0 14px; color: #606266; line-height: 1.7; }
.workflow-guide-status {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  margin-bottom: 16px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
}
.workflow-guide-status__row { display: flex; align-items: center; gap: 8px; }
.workflow-guide-status__label { color: #606266; font-size: 13px; font-weight: 600; }
.workflow-guide-status__arrow { color: #909399; }
.workflow-guide-list { margin: 0; padding-left: 22px; color: #303133; line-height: 1.8; }
.workflow-guide-list li { padding-left: 4px; }
.workflow-guide-list li + li { margin-top: 6px; }
.workflow-guide-list strong { color: var(--el-color-primary); font-weight: 600; }
.workflow-guide-list :deep(.el-tag) { vertical-align: middle; }
.workflow-guide-tabs :deep(.el-tabs__content) { min-height: 360px; }
.workflow-guide-legend { gap: 14px; }
.workflow-guide-legend__section {
  padding: 12px 14px;
  border: 1px solid #e8edf5;
  border-radius: 8px;
  background: #fff;
}
.workflow-guide-legend__title { color: #303133; font-size: 14px; font-weight: 600; }
.workflow-guide-legend__items { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
.workflow-guide-legend__item { display: flex; align-items: flex-start; gap: 8px; color: #606266; line-height: 1.7; }
.workflow-guide-legend__item :deep(.el-tag) { flex: 0 0 auto; margin-top: 2px; }
.workflow-guide-legend__priority-items { display: flex; flex-wrap: wrap; gap: 12px 20px; margin-top: 10px; color: #606266; line-height: 1.7; }
.workflow-guide-legend__priority-items > span { display: inline-flex; align-items: center; gap: 6px; }
.workflow-guide-legend__priority-items :deep(.el-tag) { flex: 0 0 auto; }
.workflow-guide :deep(.workflow-guide-priority-high) {
  --el-tag-bg-color: #f5222d;
  --el-tag-border-color: #f5222d;
  --el-tag-text-color: #fff;
}
.workflow-guide :deep(.workflow-guide-priority-medium) {
  --el-tag-bg-color: #52c41a;
  --el-tag-border-color: #52c41a;
  --el-tag-text-color: #fff;
}
.workflow-guide :deep(.workflow-guide-priority-low) {
  --el-tag-bg-color: #1677ff;
  --el-tag-border-color: #1677ff;
  --el-tag-text-color: #fff;
}

.response-raw {
  max-height: 400px; overflow: auto; background: #f5f7fa;
  padding: 12px; border-radius: 4px; font-size: 12px; white-space: pre-wrap; word-break: break-all;
}

/* 隔离 checkbox 和文案区域的点击 */
.tree-with-checkbox :deep(.el-tree-node__content) {
  pointer-events: none !important;
  user-select: none !important;
}
.tree-with-checkbox :deep(.el-tree-node__content > .el-checkbox) {
  pointer-events: auto !important;
  cursor: pointer;
  user-select: none !important;
}
.tree-with-checkbox :deep(.el-tree-node__label) {
  pointer-events: none !important;
  user-select: none !important;
}
.tree-with-checkbox :deep(.custom-tree-node) {
  pointer-events: auto !important;
}
.tree-with-checkbox :deep(.tree-node-label) {
  pointer-events: auto !important;
  cursor: pointer;
  user-select: none !important;
}
.tree-with-checkbox :deep(.tree-node-actions) {
  pointer-events: auto !important;
}

@media (max-width: 1600px) {
  .tree-card, .list-card { padding: 14px; }
  .tree-header h3, .list-header h3 { font-size: 18px; }
  .tree-node-actions { width: 78px; flex-basis: 78px; }
}

/* 移动端适配 */
@media (max-width: 768px) {
  .el-row { flex-direction: column !important; }
  .el-row .el-col { max-width: 100% !important; flex: 0 0 100% !important; margin-bottom: 12px; }
  .el-dialog { width: 95vw !important; max-width: 95vw !important; }
  .el-table { font-size: 13px; overflow-x: auto; display: block; }
  .el-pagination { justify-content: center !important; }
  .card-header, .list-header, .tree-header { flex-direction: column; align-items: flex-start; gap: 8px; }
  .header-actions, .tree-header-actions { flex-wrap: wrap; }
}
</style>
