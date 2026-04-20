import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import vm from 'node:vm'

function plain(value) {
  return JSON.parse(JSON.stringify(value))
}

function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}(`)
  assert.notEqual(start, -1, `missing ${name}`)
  const firstBrace = source.indexOf('{', start)
  let depth = 0
  for (let index = firstBrace; index < source.length; index += 1) {
    const char = source[index]
    if (char === '{') depth += 1
    if (char === '}') {
      depth -= 1
      if (depth === 0) {
        return source.slice(start, index + 1)
      }
    }
  }
  throw new Error(`could not extract ${name}`)
}

function loadProfileDialogBypassHelpers() {
  const here = dirname(fileURLToPath(import.meta.url))
  const dialogPath = resolve(here, '../components/ProfileDialog.vue')
  const dialogSource = readFileSync(dialogPath, 'utf8')
  const scriptSource = dialogSource.match(/<script setup>([\s\S]*?)<\/script>/)?.[1] || ''
  const helperSource = [
    'const bypassMatchMode = { value: "subdomains" }',
    extractFunction(scriptSource, 'normalizeBypassRulesForForm'),
    extractFunction(scriptSource, 'normalizeBypassRule'),
    extractFunction(scriptSource, 'normalizeBypassMatchMode'),
    extractFunction(scriptSource, 'normalizeBypassDomain'),
    extractFunction(scriptSource, 'upsertBypassRuleToList'),
    'module.exports = { normalizeBypassRulesForForm }',
  ].join('\n\n')

  const context = {
    URL,
    module: { exports: {} },
  }
  vm.runInNewContext(helperSource, context)
  return context.module.exports
}

test('profile dialog keeps added bypass rules instead of clearing them during save normalization', () => {
  const { normalizeBypassRulesForForm } = loadProfileDialogBypassHelpers()
  const result = normalizeBypassRulesForForm([
    { domain: 'example.com', match_mode: 'subdomains' },
    { domain: 'api.test.com', match_mode: 'exact' },
  ])

  assert.deepEqual(plain(result), [
    { domain: 'example.com', match_mode: 'subdomains' },
    { domain: 'api.test.com', match_mode: 'exact' },
  ])
})

test('profile dialog normalization accepts pasted text values and removes duplicate domains', () => {
  const { normalizeBypassRulesForForm } = loadProfileDialogBypassHelpers()
  const result = normalizeBypassRulesForForm([
    'https://Example.com/path',
    '*.example.com',
    ' exact:login.example.com ',
  ])

  assert.deepEqual(plain(result), [
    { domain: 'example.com', match_mode: 'subdomains' },
    { domain: 'login.example.com', match_mode: 'exact' },
  ])
})
