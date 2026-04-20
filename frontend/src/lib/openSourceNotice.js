const _0x4fd2 = new TextDecoder()

function _0x8a12(value) {
  const binary = atob(value)
  const bytes = Uint8Array.from(binary, item => item.charCodeAt(0))
  return _0x4fd2.decode(bytes)
}

const _0x7be1 = {
  windowTitle: 'T3Blbi1BbnRpLUJyb3dzZXIgwrcg5byA5rqQ5oyH57q55rWP6KeI5ZmoIC8gT3Blbi1zb3VyY2UgZmluZ2VycHJpbnQgYnJvd3Nlcg==',
  sidebarSubtitle: {
    'zh-CN': '5byA5rqQ5oyH57q55rWP6KeI5Zmo',
    'en-US': 'T3Blbi1zb3VyY2UgZmluZ2VycHJpbnQgYnJvd3Nlcg==',
  },
  noticeTitle: '5L2/55So5YmN6K+35YWI6ZiF6K+7IC8gUGxlYXNlIHJlYWQgYmVmb3JlIHVzZQ==',
  introZh: '5pys6aG555uu5piv5byA5rqQ6aG555uuIOS4jei/m+ihjOS7u+S9leaUtui0uQ==',
  introEn: 'VGhpcyBpcyBhbiBvcGVuLXNvdXJjZSBwcm9qZWN0IGFuZCBpdCBpcyBub3Qgc29sZCBhcyBhIHBhaWQgcHJvZHVjdA==',
  pairs: [
    {
      zh: '5pys6aG555uu5LuF55So5LqO5pys5Zyw5byA5Y+R44CB6Ieq5Yqo5YyW6LCD6K+V44CB5rWL6K+V6aqM6K+B5ZKM5ZCI6KeE56CU56m2',
      en: 'VGhpcyBwcm9qZWN0IGlzIG9ubHkgaW50ZW5kZWQgZm9yIGxvY2FsIGRldmVsb3BtZW50LCBhdXRvbWF0aW9uIGRlYnVnZ2luZywgdGVzdGluZywgYW5kIGNvbXBsaWFudCByZXNlYXJjaA==',
    },
    {
      zh: '56aB5q2i5bCG5pys6aG555uu55So5LqO6Z2e5rOV5rS75Yqo44CB5pyq5o6I5p2D6K6/6Zeu44CB5om56YeP5rul55So5bmz5Y+w6KeE5YiZ5oiW5YW25LuW5L615p2D6KGM5Li6',
      en: 'RG8gbm90IHVzZSB0aGlzIHByb2plY3QgZm9yIGlsbGVnYWwgYWN0aXZpdHksIHVuYXV0aG9yaXplZCBhY2Nlc3MsIHBsYXRmb3JtIGFidXNlLCBvciBpbmZyaW5nZW1lbnQ=',
    },
    {
      zh: '5L2/55So6ICF6ZyA6Ieq6KGM56Gu6K6k5omA5Zyo5Zyw5Yy655qE5rOV5b6L5rOV6KeE5ZKM55uu5qCH5bmz5Y+w55qE5L2/55So6KeE5YiZ',
      en: 'VXNlcnMgYXJlIHJlc3BvbnNpYmxlIGZvciBmb2xsb3dpbmcgbG9jYWwgbGF3cyBhbmQgdGhlIHJ1bGVzIG9mIGFueSBwbGF0Zm9ybSB0aGV5IGludGVyYWN0IHdpdGg=',
    },
    {
      zh: '5aaC5p6c5pyJ5Lq65Lul5Lu75L2V5b2i5byP5ZSu5Y2W5oiW5pS26LS55pys6aG555uu77yM6K+36Ieq6KGM55SE5Yir',
      en: 'SWYgc29tZW9uZSB0cmllcyB0byBzZWxsIHRoaXMgcHJvamVjdCBhcyBhIGNvbW1lcmNpYWwgcHJvZHVjdCwgcGxlYXNlIHN0YXkgaW5mb3JtZWQ=',
    },
  ],
  confirmText: '5oiR5bey5LqG6KejIC8gSSB1bmRlcnN0YW5k',
}

function _0x3e29(locale) {
  return locale === 'en-US' ? 'en-US' : 'zh-CN'
}

export function getOpenSourceWindowTitle() {
  return _0x8a12(_0x7be1.windowTitle)
}

export function getOpenSourceSidebarSubtitle(locale) {
  const currentLocale = _0x3e29(locale)
  return _0x8a12(_0x7be1.sidebarSubtitle[currentLocale])
}

export function getOpenSourceNotice() {
  return {
    title: _0x8a12(_0x7be1.noticeTitle),
    introZh: _0x8a12(_0x7be1.introZh),
    introEn: _0x8a12(_0x7be1.introEn),
    pairs: _0x7be1.pairs.map(item => ({
      zh: _0x8a12(item.zh),
      en: _0x8a12(item.en),
    })),
    confirmText: _0x8a12(_0x7be1.confirmText),
  }
}
