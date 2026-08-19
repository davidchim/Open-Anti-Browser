<template>
  <div class="sync-page">
    <section class="page-panel soft sync-hero">
      <div class="sync-hero-main">
        <div>
          <div class="sync-eyebrow">Synchronizer</div>
          <h2>{{ t('syncer.title') }}</h2>
          <p class="panel-desc">{{ t('syncer.subtitle') }}</p>
        </div>

        <div class="hero-action-row">
          <el-button type="primary" :disabled="selectedRunningIds.length < 2" :loading="submitting" @click="startSync">
            <el-icon><VideoPlay /></el-icon>
            {{ t('syncer.startSync') }}
          </el-button>
          <el-button plain :disabled="!session.running || selectedRunningIds.length < 2" :loading="submitting" @click="restartSync">
            <el-icon><RefreshRight /></el-icon>
            {{ t('syncer.restartSync') }}
          </el-button>
          <el-button plain :disabled="!session.running" :loading="submitting" @click="stopSync">
            <el-icon><CloseBold /></el-icon>
            {{ t('syncer.stopSync') }}
          </el-button>
          <el-popover
            v-model:visible="settingsVisible"
            placement="bottom-end"
            width="430"
            trigger="click"
            popper-class="sync-settings-popper"
          >
            <template #reference>
              <el-button circle plain>
                <el-icon><Setting /></el-icon>
              </el-button>
            </template>
            <div class="settings-popover">
              <div class="popover-head">
                <div>
                  <div class="popover-title">{{ t('syncer.settingsTitle') }}</div>
                  <div class="popover-subtitle">{{ t('syncer.settingsSubtitle') }}</div>
                </div>
                <el-button text @click="settingsVisible = false">{{ t('common.close') }}</el-button>
              </div>

              <div class="settings-section">
                <div class="section-title">{{ t('syncer.syncContent') }}</div>
                <div class="toggle-grid">
                  <label class="toggle-item"><span>{{ t('syncer.navigation') }}</span><el-switch v-model="settings.options.sync_navigation" /></label>
                  <label class="toggle-item"><span>{{ t('syncer.clickActions') }}</span><el-switch v-model="settings.options.sync_click" /></label>
                  <label class="toggle-item"><span>{{ t('syncer.textInput') }}</span><el-switch v-model="settings.options.sync_input" /></label>
                  <label class="toggle-item"><span>{{ t('syncer.scrollActions') }}</span><el-switch v-model="settings.options.sync_scroll" /></label>
                  <label class="toggle-item"><span>{{ t('syncer.keyboardActions') }}</span><el-switch v-model="settings.options.sync_keyboard" /></label>
                  <label class="toggle-item"><span>{{ t('syncer.mouseMovement') }}</span><el-switch v-model="settings.options.sync_mouse_move" /></label>
                  <label class="toggle-item"><span>{{ t('syncer.tabsAndAddressBar') }}</span><el-switch v-model="settings.options.sync_browser_ui" /></label>
                </div>
              </div>

              <div class="settings-section">
                <div class="section-title">{{ t('syncer.startupBehavior') }}</div>
                <label class="toggle-item single">
                  <span>{{ t('syncer.syncMasterUrlOnStart') }}</span>
                  <el-switch v-model="settings.options.sync_current_url_on_start" />
                </label>
              </div>

              <div class="settings-section">
                <div class="section-title">{{ t('syncer.actionDelay') }}</div>
                <div class="delay-card">
                  <label class="toggle-item single inline">
                    <span>{{ t('syncer.clickDelay') }}</span>
                    <el-switch v-model="settings.delayClickEnabled" />
                  </label>
                  <div class="delay-line">
                    <el-input-number v-model="settings.delayClickMin" :min="0" :max="5000" controls-position="right" />
                    <span>{{ t('syncer.to') }}</span>
                    <el-input-number v-model="settings.delayClickMax" :min="0" :max="5000" controls-position="right" />
                    <span>ms</span>
                  </div>
                </div>
                <div class="delay-card">
                  <label class="toggle-item single inline">
                    <span>{{ t('syncer.inputDelay') }}</span>
                    <el-switch v-model="settings.delayInputEnabled" />
                  </label>
                  <div class="delay-line">
                    <el-input-number v-model="settings.delayInputMin" :min="0" :max="5000" controls-position="right" />
                    <span>{{ t('syncer.to') }}</span>
                    <el-input-number v-model="settings.delayInputMax" :min="0" :max="5000" controls-position="right" />
                    <span>ms</span>
                  </div>
                </div>
              </div>

              <div class="settings-section">
                <div class="section-title">{{ t('syncer.hotkeys') }}</div>
                <div class="hotkey-grid">
                  <div v-for="item in hotkeyItems" :key="item.key" class="hotkey-item">
                    <span>{{ t(item.labelKey) }}</span>
                    <el-input v-model="settings.hotkeys[item.key]" clearable />
                  </div>
                </div>
              </div>

              <div class="popover-actions">
                <el-button @click="settingsVisible = false">{{ t('common.cancel') }}</el-button>
                <el-button type="primary" @click="saveSettings">{{ t('common.save') }}</el-button>
              </div>
            </div>
          </el-popover>
        </div>
      </div>

      <div class="sync-metrics">
        <div class="metric-card">
          <span>{{ t('syncer.selectedWindows') }}</span>
          <strong>{{ selectedRunningIds.length }}</strong>
        </div>
        <div class="metric-card">
          <span>{{ t('syncer.runningWindows') }}</span>
          <strong>{{ runningProfiles.length }}</strong>
        </div>
        <div class="metric-card">
          <span>{{ t('syncer.currentMaster') }}</span>
          <strong>{{ masterName }}</strong>
        </div>
        <div class="metric-card accent">
          <span>{{ t('syncer.status') }}</span>
          <strong>{{ syncStateLabel }}</strong>
        </div>
      </div>
    </section>

    <div class="sync-layout">
      <section class="page-panel sync-list-panel">
        <div class="panel-title-row sync-list-head">
          <div>
            <h3>{{ t('syncer.runningBrowsers') }}</h3>
            <p class="panel-desc">{{ t('syncer.selectTwoHint') }}</p>
          </div>
          <div class="list-head-actions">
            <el-select v-model="groupFilter" class="group-filter" clearable :placeholder="t('syncer.allGroups')">
              <el-option :label="t('syncer.allGroups')" value="" />
              <el-option v-for="group in groups" :key="group || '_'" :label="group || t('syncer.ungrouped')" :value="group" />
            </el-select>
            <el-button plain :disabled="!selectedRunningIds.length" @click="showWindows()">
              <el-icon><FullScreen /></el-icon>
              {{ t('syncer.showWindows') }}
            </el-button>
            <el-button plain :disabled="!selectedRunningIds.length" @click="uniformSize">
              {{ t('syncer.uniformSize') }}
            </el-button>
          </div>
        </div>

        <div class="sync-selected-bar">
          <span class="pill">{{ t('syncer.selectedCount', { n: selectedRunningIds.length }) }}</span>
          <span class="pill soft">{{ t('syncer.masterValue', { name: masterName }) }}</span>
          <span class="pill soft">{{ t('syncer.followersCount', { n: followerCountPreview }) }}</span>
        </div>

        <div class="sync-table-wrap">
          <el-table v-if="filteredProfiles.length" class="sync-table" :data="filteredProfiles" row-key="id" stripe height="100%">
            <el-table-column width="52">
              <template #header>
                <el-checkbox
                  :model-value="allVisibleSelected"
                  :indeterminate="someVisibleSelected"
                  @change="handleSelectAll"
                />
              </template>
              <template #default="{ row }">
                <el-checkbox
                  :model-value="isSelected(row.id)"
                  @change="value => handleSelect(row.id, value)"
                  @click.stop
                />
              </template>
            </el-table-column>

            <el-table-column :label="t('syncer.window')" min-width="280">
              <template #default="{ row }">
                <div class="profile-card-row">
                  <div class="profile-avatar engine">
                    <img class="profile-avatar-icon" :src="row.engine === 'chrome' ? chromeIcon : firefoxIcon" :alt="row.engine" />
                  </div>
                  <div class="profile-info">
                    <div class="profile-name-line">
                      <span class="profile-name">{{ row.name || row.id.slice(0, 8) }}</span>
                      <el-tag v-if="effectiveMasterId === row.id" size="small" type="primary" effect="plain">{{ t('syncer.master') }}</el-tag>
                    </div>
                    <div class="profile-meta">{{ row.group || t('syncer.ungrouped') }} · {{ t('syncer.debugPort') }} {{ row.runtime?.remote_debugging_port || '—' }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column :label="t('syncer.engine')" width="100">
              <template #default="{ row }">
                <el-tag :type="row.engine === 'chrome' ? 'primary' : 'warning'" effect="plain" size="small">
                  {{ row.engine === 'chrome' ? 'Chrome' : 'Firefox' }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column :label="t('syncer.connectionInfo')" min-width="220">
              <template #default="{ row }">
                <div class="status-stack">
                  <span class="status-ip">{{ row.runtime?.resolved_ip || t('syncer.unresolved') }}</span>
                  <span class="status-url">{{ row.runtime?.startup_url || row.runtime?.last_url || t('syncer.currentTabPending') }}</span>
                </div>
              </template>
            </el-table-column>

            <el-table-column :label="t('syncer.actions')" width="150" align="center" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-tooltip :content="t('syncer.setAsMaster')">
                    <el-button circle text class="row-action" @click="setMaster(row.id)">
                      <el-icon><Monitor /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip :content="t('syncer.showWindow')">
                    <el-button circle text class="row-action" @click="showWindows([row.id])">
                      <el-icon><FullScreen /></el-icon>
                    </el-button>
                  </el-tooltip>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <div v-else class="empty-state sync-empty">
            <el-icon><Monitor /></el-icon>
            <h3>{{ t('syncer.noSyncWindows') }}</h3>
            <p>{{ t('syncer.startTwoWindowsHint') }}</p>
          </div>
        </div>
      </section>

      <aside class="page-panel soft sync-console">
        <div class="console-head">
          <div>
            <h3>{{ t('syncer.console') }}</h3>
            <p class="panel-desc">{{ t('syncer.consoleDesc') }}</p>
          </div>
          <el-switch v-model="compactPanel" :active-text="t('syncer.compact')" :inactive-text="t('syncer.full')" />
        </div>

        <div class="console-status-list">
          <div class="status-card-line" :class="{ active: session.running }">
            <span class="status-dot" :class="session.running ? 'running' : ''"></span>
            <div class="status-copy">
              <span>{{ t('syncer.syncStatus') }}:</span>
              <strong>{{ syncStateLabel }}</strong>
            </div>
          </div>
          <div class="status-card-line">
            <div class="status-copy">
              <span>{{ t('syncer.connected') }}:</span>
              <strong>{{ session.connected_followers || 0 }} / {{ session.follower_count || 0 }}</strong>
            </div>
          </div>
          <div class="status-card-line wide">
            <div class="status-copy wide">
              <span>{{ t('syncer.latestAction') }}:</span>
              <strong>{{ lastEventText }}</strong>
            </div>
          </div>
        </div>

        <div class="console-primary-actions">
          <el-button type="primary" :disabled="selectedRunningIds.length < 2" :loading="submitting" @click="startSync">{{ t('syncer.startSync') }}</el-button>
          <el-button plain :disabled="!session.running || selectedRunningIds.length < 2" :loading="submitting" @click="restartSync">{{ t('syncer.restartSync') }}</el-button>
          <el-button plain :disabled="!session.running" :loading="submitting" @click="stopSync">{{ t('syncer.stopSync') }}</el-button>
        </div>

        <template v-if="compactPanel">
          <div class="compact-panel">
            <div class="quick-grid two">
              <el-button plain :disabled="!selectedRunningIds.length" @click="showWindows()">{{ t('syncer.showWindows') }}</el-button>
              <el-button plain :disabled="!selectedRunningIds.length" @click="uniformSize">{{ t('syncer.uniformSize') }}</el-button>
              <el-button plain :disabled="!selectedRunningIds.length" @click="arrangeWindows">{{ t('syncer.arrangeNow') }}</el-button>
              <el-button plain :disabled="!selectedRunningIds.length" @click="runTabAction('close_blank')">{{ t('syncer.closeBlankTabs') }}</el-button>
            </div>
          </div>
        </template>

        <template v-else>
          <el-segmented
            v-model="activePanel"
            class="console-tabs"
            :options="panelOptions"
          />

          <div v-if="activePanel === 'windows'" class="panel-stack">
            <section class="console-card">
              <div class="card-title">{{ t('syncer.quickActions') }}</div>
              <div class="quick-grid two">
                <el-button plain :disabled="!selectedRunningIds.length" @click="showWindows()">{{ t('syncer.showWindows') }}</el-button>
                <el-button plain :disabled="!selectedRunningIds.length" @click="uniformSize">{{ t('syncer.uniformSize') }}</el-button>
              </div>
            </section>

            <section class="console-card">
              <div class="card-title">{{ t('syncer.windowArrangement') }}</div>
              <el-form label-position="top" class="panel-form">
                <el-form-item :label="t('syncer.monitor')">
                  <el-select v-model="windowForm.monitorId" :placeholder="t('syncer.selectMonitor')">
                    <el-option v-for="monitor in monitors" :key="monitor.id" :label="monitorText(monitor)" :value="monitor.id" />
                  </el-select>
                </el-form-item>
                <el-form-item :label="t('syncer.arrangement')">
                  <el-radio-group v-model="windowForm.arrangeMode" class="arrange-radio">
                    <el-radio-button value="grid">{{ t('syncer.grid') }}</el-radio-button>
                    <el-radio-button value="overlap">{{ t('syncer.overlap') }}</el-radio-button>
                  </el-radio-group>
                </el-form-item>
              </el-form>
              <el-button class="wide-btn" type="primary" plain :disabled="!selectedRunningIds.length" @click="arrangeWindows">{{ t('syncer.arrangeNow') }}</el-button>
            </section>
          </div>

          <div v-else-if="activePanel === 'text'" class="panel-stack">
            <section class="console-card">
              <div class="card-title">{{ t('syncer.commonInput') }}</div>
              <div class="quick-grid two">
                <el-button plain :disabled="!selectedRunningIds.length" @click="runTextAction({ action: 'clear' })">{{ t('syncer.clearContent') }}</el-button>
                <el-button plain :disabled="!selectedRunningIds.length || !sameText.trim()" @click="runTextAction({ action: 'same', text: sameText })">{{ t('syncer.sameContent') }}</el-button>
              </div>
            </section>

            <section class="console-card">
              <div class="card-title">{{ t('syncer.randomNumbers') }}</div>
              <div class="range-row">
                <el-input-number v-model="randomRange.start" :precision="3" :step="0.001" controls-position="right" />
                <span class="range-sep">{{ t('syncer.to') }}</span>
                <el-input-number v-model="randomRange.end" :precision="3" :step="0.001" controls-position="right" />
              </div>
              <el-button class="wide-btn" plain :disabled="!selectedRunningIds.length" @click="runTextAction({ action: 'random', range_start: randomRange.start, range_end: randomRange.end, precision: 3 })">{{ t('syncer.enterRandomNumbers') }}</el-button>
            </section>

            <section class="console-card">
              <div class="card-title">{{ t('syncer.sameText') }}</div>
              <el-input v-model="sameText" type="textarea" :rows="3" :placeholder="t('syncer.sameTextPlaceholder')" />
              <div class="card-actions right">
                <el-button type="primary" plain :disabled="!selectedRunningIds.length || !sameText.trim()" @click="runTextAction({ action: 'same', text: sameText })">{{ t('syncer.enter') }}</el-button>
              </div>
            </section>

            <section class="console-card">
              <div class="card-title">{{ t('syncer.designatedTextGroups') }}</div>
              <el-radio-group v-model="designatedMode" class="mode-radio">
                <el-radio-button value="sequential">{{ t('syncer.sequential') }}</el-radio-button>
                <el-radio-button value="random">{{ t('syncer.random') }}</el-radio-button>
                <el-radio-button value="fixed">{{ t('syncer.fixed') }}</el-radio-button>
              </el-radio-group>
              <el-input v-if="designatedMode === 'fixed'" v-model="fixedText" :placeholder="t('syncer.fixedTextPlaceholder')" />
              <div class="text-groups">
                <div v-for="(group, index) in designatedGroups" :key="group.id" class="text-group-card">
                  <div class="text-group-head">
                    <span>{{ t('syncer.textGroup', { n: index + 1 }) }}</span>
                    <el-button text :disabled="designatedGroups.length === 1" @click="removeGroup(group.id)">{{ t('common.delete') }}</el-button>
                  </div>
                  <el-input v-model="group.content" type="textarea" :rows="4" :placeholder="t('syncer.oneItemPerLine')" />
                </div>
              </div>
              <el-button class="wide-btn dashed" plain @click="addGroup">{{ t('syncer.addTextGroup') }}</el-button>
              <div class="card-actions right">
                <el-button type="primary" plain :disabled="!selectedRunningIds.length" @click="runTextAction({ action: 'designated', groups: designatedGroups, designated_mode: designatedMode, fixed_text: fixedText })">{{ t('syncer.executeInput') }}</el-button>
              </div>
            </section>
          </div>

          <div v-else class="panel-stack">
            <section class="console-card">
              <div class="card-title">{{ t('syncer.tabCleanup') }}</div>
              <div class="quick-grid two">
                <el-button plain :disabled="!selectedRunningIds.length" @click="runTabAction('unify_tabs')">{{ t('syncer.unifyTabs') }}</el-button>
                <el-button plain :disabled="!selectedRunningIds.length" @click="runTabAction('close_others')">{{ t('syncer.closeOthers') }}</el-button>
                <el-button plain :disabled="!selectedRunningIds.length" @click="runTabAction('close_current')">{{ t('syncer.closeCurrent') }}</el-button>
                <el-button plain :disabled="!selectedRunningIds.length" @click="runTabAction('close_blank')">{{ t('syncer.closeBlankTabs') }}</el-button>
              </div>
            </section>

            <section class="console-card">
              <div class="card-title">{{ t('syncer.openUrlsInBulk') }}</div>
              <el-input v-model="urlInput" type="textarea" :rows="4" :placeholder="t('syncer.oneUrlPerLine')" />
              <label class="toggle-item single block-gap">
                <span>{{ t('syncer.firstUrlInCurrentTab') }}</span>
                <el-switch v-model="firstInCurrentTab" />
              </label>
              <el-button class="wide-btn" plain :disabled="!selectedRunningIds.length || !parsedUrls.length" @click="openUrls">{{ t('syncer.openInBulk') }}</el-button>
            </section>
          </div>
        </template>

        <el-alert v-if="session.last_error" class="console-error" type="error" show-icon :closable="false">{{ localizedLastError }}</el-alert>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onActivated, onDeactivated, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CloseBold, FullScreen, Monitor, RefreshRight, Setting, VideoPlay } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useProfileStore } from '../stores/profile.js'
import chromeIcon from '../assets/chrome.svg'
import firefoxIcon from '../assets/firefox.png'

const store = useProfileStore()
const { t, locale } = useI18n()
const groupFilter = ref('')
const selectedIds = ref([])
const masterId = ref('')
const activePanel = ref('windows')
const settingsVisible = ref(false)
const compactPanel = ref(false)
const submitting = ref(false)
const urlInput = ref('')
const sameText = ref('')
const firstInCurrentTab = ref(true)
const designatedMode = ref('sequential')
const fixedText = ref('')
const designatedGroups = ref([{ id: crypto.randomUUID(), content: '' }])
const randomRange = reactive({ start: 0.001, end: 0.009 })
const windowForm = reactive({ monitorId: '', arrangeMode: 'grid' })

let pollTimer = null
let pollRound = 0
let hotkeysBound = false
const componentActive = ref(false)

const SETTINGS_KEY = 'oab.sync.settings.v6'
const UI_KEY = 'oab.sync.ui.v6'

const settings = reactive(loadSettings())
const hotkeyItems = [
  { key: 'start_sync', labelKey: 'syncer.hotkeyStart' },
  { key: 'stop_sync', labelKey: 'syncer.hotkeyStop' },
  { key: 'restart_sync', labelKey: 'syncer.hotkeyRestart' },
  { key: 'toggle_panel', labelKey: 'syncer.hotkeyTogglePanel' },
  { key: 'arrange_windows', labelKey: 'syncer.hotkeyArrange' },
  { key: 'random_input', labelKey: 'syncer.hotkeyRandomInput' },
  { key: 'same_text', labelKey: 'syncer.hotkeySameText' },
  { key: 'unify_tabs', labelKey: 'syncer.hotkeyUnifyTabs' },
  { key: 'close_others', labelKey: 'syncer.hotkeyCloseOthers' },
  { key: 'close_current', labelKey: 'syncer.hotkeyCloseCurrent' },
  { key: 'close_blank', labelKey: 'syncer.hotkeyCloseBlank' },
]

const session = computed(() => store.synchronizer || { running: false, follower_count: 0, connected_followers: 0, last_event: null, last_error: '' })
const runningProfiles = computed(() => (store.profiles || []).filter(item => item.status === 'running' && item.runtime?.remote_debugging_port))
const groups = computed(() => Array.from(new Set(runningProfiles.value.map(item => item.group || '').values())).filter(Boolean).sort((a, b) => a.localeCompare(b)))
const filteredProfiles = computed(() => runningProfiles.value.filter(item => !groupFilter.value || (item.group || '') === groupFilter.value))
const visibleIds = computed(() => filteredProfiles.value.map(item => item.id))
const selectedRunningIds = computed(() => selectedIds.value.filter(id => runningProfiles.value.some(item => item.id === id)))
const allVisibleSelected = computed(() => visibleIds.value.length > 0 && visibleIds.value.every(id => selectedIds.value.includes(id)))
const someVisibleSelected = computed(() => {
  if (!visibleIds.value.length) return false
  const count = visibleIds.value.filter(id => selectedIds.value.includes(id)).length
  return count > 0 && count < visibleIds.value.length
})
const effectiveMasterId = computed(() => {
  if (masterId.value && selectedRunningIds.value.includes(masterId.value)) return masterId.value
  if (session.value.master_profile_id && selectedRunningIds.value.includes(session.value.master_profile_id)) return session.value.master_profile_id
  return selectedRunningIds.value[0] || masterId.value || session.value.master_profile_id || ''
})
const monitors = computed(() => store.syncMonitors || [])
const parsedUrls = computed(() => urlInput.value.split(/\r?\n/).map(item => item.trim()).filter(Boolean))
const masterName = computed(() => runningProfiles.value.find(item => item.id === effectiveMasterId.value)?.name || '—')
const followerCountPreview = computed(() => Math.max(0, selectedRunningIds.value.length - (effectiveMasterId.value ? 1 : 0)))
const panelOptions = computed(() => [
  { label: t('syncer.windowManagement'), value: 'windows' },
  { label: t('syncer.textManagement'), value: 'text' },
  { label: t('syncer.tabManagement'), value: 'tabs' },
])
const syncStateLabel = computed(() => session.value.running ? t('syncer.running') : t('syncer.stopped'))
const lastEventText = computed(() => {
  const event = session.value.last_event
  if (!event?.type) return t('syncer.none')
  const labels = {
    navigate: 'syncer.eventNavigate',
    manual_navigate: 'syncer.eventOpenUrl',
    sync_current_url: 'syncer.eventSyncUrl',
    browser_close_current: 'syncer.eventCloseTab',
    click: 'syncer.eventClick',
    input: 'syncer.eventInput',
    change: 'syncer.eventFormChange',
    wheel: 'syncer.eventScroll',
    scroll: 'syncer.eventScroll',
    keydown: 'syncer.eventKeyboard',
    mouse_move: 'syncer.eventMouseMovement',
  }
  const label = labels[event.type] ? t(labels[event.type]) : event.type
  const summary = localizeEventSummary(event.summary)
  return summary ? `${label} · ${summary}` : label
})
const localizedLastError = computed(() => localizeSyncError(session.value.last_error))

watch(() => session.value.master_profile_id, value => {
  if (value) masterId.value = value
})
watch([compactPanel, activePanel, () => windowForm.monitorId, () => windowForm.arrangeMode, firstInCurrentTab, groupFilter], saveUiState)
watch(() => session.value.running, () => {
  if (componentActive.value) {
    startPolling()
  }
})
watch(() => runningProfiles.value.map(item => item.id).join('|'), pruneSelection)

onActivated(async () => {
  componentActive.value = true
  loadUiState()
  bindHotkeys()
  pruneSelection()
  try {
    if (!store.synchronizer || typeof store.synchronizer.running === 'undefined') {
      await store.refreshSynchronizer()
    }
    if (!monitors.value.length) {
      await store.refreshSyncMonitors()
    }
    if (!store.profiles?.length) {
      await store.refreshProfiles()
    }
  } catch {
    // ignore activation refresh errors
  }
  pruneSelection()
  startPolling()
})

onDeactivated(() => {
  componentActive.value = false
  stopPolling()
  unbindHotkeys()
})

onUnmounted(() => {
  stopPolling()
  unbindHotkeys()
})

function loadSettings() {
  const defaults = {
    options: {
      sync_navigation: true,
      sync_click: true,
      sync_input: true,
      sync_scroll: true,
      sync_keyboard: true,
      sync_mouse_move: false,
      sync_current_url_on_start: true,
      sync_browser_ui: true,
    },
    delayClickEnabled: false,
    delayClickMin: 100,
    delayClickMax: 300,
    delayInputEnabled: false,
    delayInputMin: 300,
    delayInputMax: 300,
    hotkeys: {
      start_sync: 'Ctrl+Alt+S',
      stop_sync: 'Ctrl+Alt+D',
      restart_sync: 'Ctrl+Alt+R',
      toggle_panel: 'Ctrl+Alt+E',
      arrange_windows: 'Ctrl+Alt+Z',
      random_input: 'Ctrl+Alt+F',
      same_text: 'Ctrl+Alt+G',
      unify_tabs: 'Ctrl+Alt+X',
      close_others: 'Ctrl+Alt+B',
      close_current: 'Ctrl+Alt+H',
      close_blank: 'Ctrl+Alt+N',
    },
  }
  try {
    const raw = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}')
    return {
      ...defaults,
      ...raw,
      options: { ...defaults.options, ...(raw.options || {}) },
      hotkeys: { ...defaults.hotkeys, ...(raw.hotkeys || {}) },
    }
  } catch {
    return defaults
  }
}

function loadUiState() {
  try {
    const raw = JSON.parse(localStorage.getItem(UI_KEY) || '{}')
    compactPanel.value = !!raw.compactPanel
    activePanel.value = raw.activePanel || 'windows'
    windowForm.monitorId = raw.monitorId || ''
    windowForm.arrangeMode = raw.arrangeMode || 'grid'
    firstInCurrentTab.value = raw.firstInCurrentTab ?? true
    groupFilter.value = raw.groupFilter || ''
  } catch {
    // ignore
  }
}

function saveUiState() {
  localStorage.setItem(UI_KEY, JSON.stringify({
    compactPanel: compactPanel.value,
    activePanel: activePanel.value,
    monitorId: windowForm.monitorId,
    arrangeMode: windowForm.arrangeMode,
    firstInCurrentTab: firstInCurrentTab.value,
    groupFilter: groupFilter.value,
  }))
}

function saveSettings() {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
  settingsVisible.value = false
  ElMessage.success(t('syncer.settingsSaved'))
}

async function refreshAll(forceProfiles = false) {
  const tasks = [store.refreshSynchronizer()]
  const hasRuntimeActivity = session.value.running || runningProfiles.value.length > 0 || selectedRunningIds.value.length > 0
  const shouldRefreshProfiles = forceProfiles || pollRound % (hasRuntimeActivity ? 5 : 12) === 0
  const shouldRefreshMonitors = forceProfiles || !monitors.value.length
  if (shouldRefreshProfiles) tasks.push(store.refreshProfiles())
  if (shouldRefreshMonitors) tasks.push(store.refreshSyncMonitors())
  await Promise.all(tasks)
  pruneSelection()
}

function startPolling() {
  stopPolling()
  pollRound = 0
  const interval = session.value.running
    ? 2200
    : (runningProfiles.value.length ? 4200 : 9000)
  pollTimer = window.setInterval(async () => {
    if (!componentActive.value || document.hidden) return
    pollRound += 1
    try {
      await refreshAll(false)
    } catch {
      // ignore polling errors
    }
  }, interval)
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function bindHotkeys() {
  if (hotkeysBound) return
  window.addEventListener('keydown', onHotkey, true)
  hotkeysBound = true
}

function unbindHotkeys() {
  if (!hotkeysBound) return
  window.removeEventListener('keydown', onHotkey, true)
  hotkeysBound = false
}

function pruneSelection() {
  const available = new Set(runningProfiles.value.map(item => item.id))
  const nextSelected = selectedIds.value.filter(id => available.has(id))
  if (nextSelected.length !== selectedIds.value.length) selectedIds.value = nextSelected
  if (masterId.value && !nextSelected.includes(masterId.value)) {
    masterId.value = nextSelected[0] || ''
  }
}

function isSelected(profileId) {
  return selectedIds.value.includes(profileId)
}

function handleSelect(profileId, checked) {
  const next = new Set(selectedIds.value)
  if (checked) next.add(profileId)
  else next.delete(profileId)
  selectedIds.value = Array.from(next).filter(id => runningProfiles.value.some(item => item.id === id))
  if (checked && !masterId.value) masterId.value = profileId
  if (masterId.value && !selectedIds.value.includes(masterId.value)) masterId.value = selectedIds.value[0] || ''
}

function handleSelectAll(checked) {
  const next = new Set(selectedIds.value)
  if (checked) visibleIds.value.forEach(id => next.add(id))
  else visibleIds.value.forEach(id => next.delete(id))
  selectedIds.value = Array.from(next).filter(id => runningProfiles.value.some(item => item.id === id))
  if (!masterId.value && selectedIds.value.length) masterId.value = selectedIds.value[0]
  if (masterId.value && !selectedIds.value.includes(masterId.value)) masterId.value = selectedIds.value[0] || ''
}

function setMaster(id) {
  masterId.value = id
  if (!selectedIds.value.includes(id)) {
    selectedIds.value = [...selectedIds.value, id]
  }
}

function syncPayload() {
  if (selectedRunningIds.value.length < 2) throw new Error(t('syncer.selectTwoError'))
  const master = effectiveMasterId.value || selectedRunningIds.value[0]
  const followers = selectedRunningIds.value.filter(id => id !== master)
  if (!followers.length) throw new Error(t('syncer.selectTwoError'))
  return {
    master_profile_id: master,
    follower_profile_ids: followers,
    options: {
      ...settings.options,
      delay_click_enabled: settings.delayClickEnabled,
      delay_click_min_ms: settings.delayClickMin,
      delay_click_max_ms: settings.delayClickMax,
      delay_input_enabled: settings.delayInputEnabled,
      delay_input_min_ms: settings.delayInputMin,
      delay_input_max_ms: settings.delayInputMax,
    },
  }
}

async function startSync() {
  submitting.value = true
  try {
    await store.startSynchronizer(syncPayload())
    startPolling()
    ElMessage.success(t('syncer.started'))
  } catch (error) {
    ElMessage.error(localizeSyncError(error.message))
  } finally {
    submitting.value = false
  }
}

async function stopSync() {
  submitting.value = true
  try {
    await store.stopSynchronizer()
    startPolling()
    ElMessage.success(t('syncer.stoppedMessage'))
  } catch (error) {
    ElMessage.error(localizeSyncError(error.message))
  } finally {
    submitting.value = false
  }
}

async function restartSync() {
  submitting.value = true
  try {
    if (session.value.running) await store.stopSynchronizer()
    await store.startSynchronizer(syncPayload())
    startPolling()
    ElMessage.success(t('syncer.restarted'))
  } catch (error) {
    ElMessage.error(localizeSyncError(error.message))
  } finally {
    submitting.value = false
  }
}

async function showWindows(ids = selectedRunningIds.value) {
  if (!ids.length) return ElMessage.warning(t('syncer.selectWindowsFirst'))
  try {
    await store.showSyncWindows(ids)
    ElMessage.success(t('syncer.actionCompleted'))
  } catch (error) {
    ElMessage.error(localizeSyncError(error.message))
  }
}

async function uniformSize() {
  if (!selectedRunningIds.value.length) return ElMessage.warning(t('syncer.selectWindowsFirst'))
  try {
    await store.uniformSyncWindows(selectedRunningIds.value)
    ElMessage.success(t('syncer.actionCompleted'))
  } catch (error) {
    ElMessage.error(localizeSyncError(error.message))
  }
}

async function arrangeWindows() {
  if (!selectedRunningIds.value.length) return ElMessage.warning(t('syncer.selectWindowsFirst'))
  try {
    await store.arrangeSyncWindows({
      profile_ids: selectedRunningIds.value,
      monitor_id: windowForm.monitorId,
      arrange_mode: windowForm.arrangeMode,
    })
    ElMessage.success(t('syncer.actionCompleted'))
  } catch (error) {
    ElMessage.error(localizeSyncError(error.message))
  }
}

async function runTextAction(payload) {
  if (!selectedRunningIds.value.length) return ElMessage.warning(t('syncer.selectWindowsFirst'))
  try {
    await store.runSyncTextAction({ profile_ids: selectedRunningIds.value, ...payload })
    ElMessage.success(t('syncer.actionCompleted'))
  } catch (error) {
    ElMessage.error(localizeSyncError(error.message))
  }
}

async function runTabAction(action) {
  if (!selectedRunningIds.value.length) return ElMessage.warning(t('syncer.selectWindowsFirst'))
  try {
    await store.runSyncTabAction({
      profile_ids: selectedRunningIds.value,
      action,
      master_profile_id: effectiveMasterId.value,
    })
    ElMessage.success(t('syncer.actionCompleted'))
  } catch (error) {
    ElMessage.error(localizeSyncError(error.message))
  }
}

async function openUrls() {
  if (!selectedRunningIds.value.length) return ElMessage.warning(t('syncer.selectWindowsFirst'))
  try {
    await store.runSyncTabAction({
      profile_ids: selectedRunningIds.value,
      action: 'open_urls',
      urls: parsedUrls.value,
      first_in_current: firstInCurrentTab.value,
    })
    ElMessage.success(t('syncer.actionCompleted'))
  } catch (error) {
    ElMessage.error(localizeSyncError(error.message))
  }
}

function addGroup() {
  designatedGroups.value.push({
    id: crypto.randomUUID(),
    content: '',
  })
}

function removeGroup(id) {
  if (designatedGroups.value.length === 1) return
  designatedGroups.value = designatedGroups.value.filter(item => item.id !== id)
}

function monitorText(monitor) {
  const work = monitor?.work_area || {}
  return `${monitor.name}${monitor.primary ? ` · ${t('syncer.primaryMonitor')}` : ''}${work.width ? ` ${work.width}×${work.height}` : ''}`
}

function localizeSyncError(message) {
  const value = String(message || '')
  if (locale.value !== 'en-US') return value
  const exactMessages = {
    '\u8bf7\u9009\u62e9\u4e3b\u6d4f\u89c8\u5668': t('syncer.errorSelectMaster'),
    '\u8bf7\u81f3\u5c11\u9009\u62e9\u4e00\u4e2a\u8ddf\u968f\u6d4f\u89c8\u5668': t('syncer.errorSelectFollower'),
    '\u8bf7\u8f93\u5165\u7f51\u5740': t('syncer.errorEnterUrl'),
    '\u540c\u6b65\u5668\u8fd8\u6ca1\u6709\u542f\u52a8': t('syncer.errorNotStarted'),
    '\u4e3b\u6d4f\u89c8\u5668\u4e0d\u53ef\u7528': t('syncer.errorMasterUnavailable'),
    '\u4e3b\u6d4f\u89c8\u5668\u5f53\u524d\u6807\u7b7e\u9875\u6ca1\u6709\u53ef\u540c\u6b65\u7684\u7f51\u5740': t('syncer.errorNoMasterUrl'),
    '\u4e3b\u6d4f\u89c8\u5668\u8fd8\u6ca1\u6709\u542f\u52a8\uff0c\u65e0\u6cd5\u5f00\u542f\u540c\u6b65\u5668': t('syncer.errorMasterNotRunning'),
    '\u8bf7\u81f3\u5c11\u9009\u62e9\u4e00\u4e2a\u5df2\u542f\u52a8\u7684\u6d4f\u89c8\u5668': t('syncer.errorSelectRunningBrowser'),
    '\u8bf7\u5148\u586b\u5199\u6307\u5b9a\u6587\u672c\u5185\u5bb9': t('syncer.errorEnterDesignatedText'),
  }
  if (exactMessages[value]) return exactMessages[value]
  return /[\u3400-\u9fff]/.test(value) ? t('syncer.operationFailed') : value
}

function localizeEventSummary(summary) {
  const value = String(summary || '')
  if (!value || locale.value !== 'en-US') return value
  const closedTabs = value.match(/^\u5df2\u5173\u95ed\s*(\d+)\s*\u4e2a\u6807\u7b7e\u9875$/)
  if (closedTabs) return t('syncer.closedTabs', { n: Number(closedTabs[1]) })
  return /[\u3400-\u9fff]/.test(value) ? '' : value
}

function normalizeShortcut(value) {
  return String(value || '').toLowerCase().replace(/\s+/g, '').replace('control', 'ctrl')
}

function matchShortcut(event, shortcut) {
  const normalized = normalizeShortcut(shortcut)
  if (!normalized) return false
  const parts = normalized.split('+').filter(Boolean)
  const last = parts[parts.length - 1]
  if (!!event.ctrlKey !== parts.includes('ctrl')) return false
  if (!!event.altKey !== parts.includes('alt')) return false
  if (!!event.shiftKey !== parts.includes('shift')) return false
  if (!!event.metaKey !== (parts.includes('meta') || parts.includes('cmd') || parts.includes('win'))) return false
  return String(event.key || '').toLowerCase() === last
}

function onHotkey(event) {
  if (!componentActive.value) return
  const target = event.target
  const tagName = String(target?.tagName || '').toLowerCase()
  const isTypingTarget = !!target?.isContentEditable || ['input', 'textarea', 'select'].includes(tagName)
  if (isTypingTarget) return
  for (const item of hotkeyItems) {
    if (!matchShortcut(event, settings.hotkeys[item.key])) continue
    event.preventDefault()
    if (item.key === 'start_sync') return startSync()
    if (item.key === 'stop_sync') return stopSync()
    if (item.key === 'restart_sync') return restartSync()
    if (item.key === 'toggle_panel') {
      compactPanel.value = !compactPanel.value
      return
    }
    if (item.key === 'arrange_windows') return arrangeWindows()
    if (item.key === 'random_input') return runTextAction({ action: 'random', range_start: randomRange.start, range_end: randomRange.end, precision: 3 })
    if (item.key === 'same_text') return runTextAction({ action: 'same', text: sameText.value })
    if (item.key === 'unify_tabs') return runTabAction('unify_tabs')
    if (item.key === 'close_others') return runTabAction('close_others')
    if (item.key === 'close_current') return runTabAction('close_current')
    if (item.key === 'close_blank') return runTabAction('close_blank')
  }
}
</script>

<style scoped>
.sync-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sync-page :deep(.page-panel),
.sync-page :deep(.page-panel.soft) {
  background: var(--oab-panel-solid-bg) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  box-shadow: none !important;
  transition: none !important;
}

.sync-page :deep(.el-button),
.sync-page :deep(.el-input__wrapper),
.sync-page :deep(.el-select__wrapper),
.sync-page :deep(.el-textarea__inner),
.sync-page :deep(.el-input-number__decrease),
.sync-page :deep(.el-input-number__increase),
.sync-page :deep(.el-segmented),
.sync-page :deep(.el-radio-button__inner),
.sync-page :deep(.el-table),
.sync-page :deep(.el-table__inner-wrapper),
.sync-page :deep(.el-table .el-table__row),
.sync-page :deep(.el-tag) {
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  box-shadow: none !important;
  transition: none !important;
}

.sync-page :deep(.el-button:hover),
.sync-page :deep(.el-button:active),
.sync-page :deep(.el-input-group__append:active),
.sync-page :deep(.el-radio-button__inner:hover) {
  transform: none !important;
  box-shadow: none !important;
}

.sync-hero {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sync-hero-main,
.sync-list-head,
.console-head,
.popover-head,
.text-group-head,
.card-actions,
.toggle-item,
.status-card-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.sync-eyebrow {
  color: var(--oab-accent);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.sync-hero h2,
.console-head h3 {
  margin: 0;
  color: var(--oab-text);
  letter-spacing: -0.35px;
}

.sync-hero h2 {
  font-size: 28px;
}

.console-head h3 {
  font-size: 18px;
}

.hero-action-row,
.list-head-actions,
.console-primary-actions,
.sync-selected-bar,
.row-actions,
.popover-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.hero-action-row {
  justify-content: flex-end;
}

.sync-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  min-height: 78px;
  padding: 14px 16px;
  border-radius: var(--oab-radius-lg);
  border: 1px solid var(--oab-border);
  background: var(--oab-card-bg);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
}

.metric-card span,
.status-card-line span,
.popover-subtitle {
  color: var(--oab-muted);
  font-size: 12px;
  line-height: 1.5;
}

.metric-card strong,
.status-card-line strong {
  color: var(--oab-text);
  font-size: 13px;
  font-weight: 650;
  line-height: 1.4;
  word-break: break-word;
}

.metric-card strong {
  font-size: 17px;
  font-weight: 700;
}

.metric-card.accent {
  border-color: rgba(0, 122, 255, 0.18);
  background: var(--oab-accent-soft);
}

.sync-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 410px;
  gap: 16px;
  align-items: start;
}

.sync-list-panel,
.sync-console {
  min-height: 680px;
}

.sync-console {
  position: sticky;
  top: 12px;
}

.group-filter {
  width: 170px;
}

.sync-selected-bar {
  margin: -4px 0 14px;
}

.pill {
  min-height: 30px;
  padding: 6px 11px;
  border-radius: 999px;
  background: var(--oab-accent-soft);
  color: var(--oab-accent);
  font-size: 12px;
  font-weight: 600;
}

.pill.soft {
  background: var(--oab-card-bg);
  color: var(--oab-text-secondary);
  border: 1px solid var(--oab-border);
}

.sync-table-wrap {
  height: calc(100vh - 365px);
  min-height: 520px;
  border-radius: var(--oab-radius-lg);
  border: 1px solid var(--oab-border);
  background: var(--oab-card-bg);
  overflow: hidden;
}

.sync-table {
  width: 100%;
}

.profile-info {
  min-width: 0;
}

.profile-name-line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.status-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 5px;
}

.status-ip {
  color: var(--oab-text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.status-url {
  max-width: 320px;
  color: var(--oab-muted);
  font-size: 12px;
  line-height: 1.45;
  word-break: break-all;
}

.row-actions {
  justify-content: center;
}

.row-action {
  color: var(--oab-accent);
}

.sync-empty {
  min-height: 100%;
}

.console-status-list,
.panel-stack,
.settings-popover,
.settings-section,
.compact-panel,
.text-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.console-status-list {
  margin: 14px 0;
}

.status-card-line {
  justify-content: flex-start;
  padding: 12px 14px;
  border-radius: var(--oab-radius-md);
  border: 1px solid var(--oab-border);
  background: var(--oab-card-bg);
}

.status-copy {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.status-copy.wide {
  align-items: flex-start;
}

.status-card-line.active {
  border-color: rgba(52, 199, 89, 0.18);
  background: rgba(52, 199, 89, 0.08);
}

.status-card-line.wide {
  align-items: flex-start;
}

.console-primary-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.console-primary-actions :deep(.el-button) {
  width: 100%;
  height: 40px;
  border-radius: 14px;
  margin-left: 0 !important;
}

.console-tabs {
  width: 100%;
  margin-bottom: 14px;
}

.console-card,
.delay-card,
.text-group-card {
  padding: 15px;
  border-radius: var(--oab-radius-lg);
  border: 1px solid var(--oab-border);
  background: var(--oab-card-bg);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card-title,
.popover-title,
.section-title {
  color: var(--oab-text);
  font-weight: 700;
}

.card-title,
.popover-title {
  font-size: 15px;
}

.section-title {
  font-size: 14px;
}

.quick-grid,
.toggle-grid,
.hotkey-grid,
.range-row {
  display: grid;
  gap: 10px;
}

.quick-grid.two,
.toggle-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.list-head-actions :deep(.el-button) {
  min-width: 112px;
  height: 38px;
  border-radius: 14px;
  padding-inline: 16px;
  margin-left: 0 !important;
  white-space: nowrap;
}

.quick-grid :deep(.el-button) {
  width: 100%;
  min-width: 0;
  height: 40px;
  border-radius: 14px;
  margin-left: 0 !important;
  padding-inline: 14px;
  justify-content: center;
  white-space: nowrap;
}

.range-row {
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
}

.range-sep,
.delay-line {
  color: var(--oab-muted);
  font-size: 13px;
}

.wide-btn {
  width: 100%;
  height: 40px;
}

.wide-btn.dashed {
  border-style: dashed;
}

.card-actions.right {
  justify-content: flex-end;
}

.toggle-item {
  padding: 12px 13px;
  border-radius: var(--oab-radius-md);
  border: 1px solid var(--oab-border);
  background: var(--oab-panel-soft-bg);
  color: var(--oab-text-secondary);
  font-size: 13px;
  font-weight: 500;
}

.toggle-item.single,
.toggle-item.inline {
  width: 100%;
}

.toggle-item.block-gap {
  margin-top: 2px;
}

.delay-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hotkey-grid {
  grid-template-columns: 1fr;
}

.hotkey-item {
  display: grid;
  grid-template-columns: 118px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  color: var(--oab-text-secondary);
  font-size: 13px;
}

.popover-actions {
  justify-content: flex-end;
}

.console-error {
  margin-top: 14px;
}

:global(.sync-settings-popper) {
  padding: 14px !important;
  border-radius: var(--oab-radius-xl) !important;
  border: 1px solid var(--oab-border) !important;
  background: var(--oab-panel-solid-bg) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  box-shadow: none !important;
}

@media (max-width: 1320px) {
  .sync-layout {
    grid-template-columns: 1fr;
  }

  .sync-console {
    position: static;
  }
}

@media (max-width: 1100px) {
  .sync-hero-main,
  .sync-list-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .hero-action-row,
  .list-head-actions {
    justify-content: flex-start;
  }

  .sync-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 920px) {
  .sync-metrics,
  .quick-grid.two,
  .toggle-grid,
  .range-row,
  .console-primary-actions,
  .hotkey-item {
    grid-template-columns: 1fr;
  }

  .sync-table-wrap {
    min-height: 480px;
    height: auto;
  }
}
</style>
