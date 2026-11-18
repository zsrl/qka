import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: 'QKA 快量化',
  description: '简洁易用的 A 股量化回测与因子投研框架',
  base: '/qka/',
  vite: {
    server: {
      port: 15000,
      host: '0.0.0.0'
    }
  },
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/qka/logo.svg' }],
    ['meta', { name: 'theme-color', content: '#0ea5e9' }]
  ],
  themeConfig: {
    logo: '/logo.svg',
    nav: [
      { text: '首页', link: '/' },
      { text: '🖥️ Web 控制台', link: '/guide/console' },
      { text: '使用指南', link: '/guide/intro' },
      {
        text: '核心功能',
        items: [
          { text: '行情数据与缓存', link: '/guide/data' },
          { text: '技术指标与因子', link: '/guide/indicators' },
          { text: '模拟行情 (Simulate)', link: '/guide/simulate' },
          { text: '策略编写规范', link: '/guide/strategy' },
          { text: '交易与仓位管理', link: '/guide/broker' },
          { text: '回测与可视化报告', link: '/guide/backtest' },
          { text: '量化分析模块', link: '/guide/analysis' },
          { text: '避坑指南与最佳实践', link: '/guide/best-practices' }
        ]
      },
      { text: 'API 参考', link: '/api/' },
      { text: '🤖 Agent 技能', link: '/guide/agent-skill' }
    ],

    sidebar: {
      '/guide/': [
        {
          text: '起步',
          items: [
            { text: '项目简介', link: '/guide/intro' },
            { text: '快速上手', link: '/guide/quick-start' },
            { text: '🖥️ Web 控制台', link: '/guide/console' },
            { text: '架构设计', link: '/guide/architecture' }
          ]
        },
        {
          text: '数据与因子',
          items: [
            { text: '多源行情与智能缓存', link: '/guide/data' },
            { text: '技术指标与因子计算', link: '/guide/indicators' },
            { text: '模拟标的 (Simulate)', link: '/guide/simulate' }
          ]
        },
        {
          text: '策略与交易',
          items: [
            { text: '策略基类与生命周期', link: '/guide/strategy' },
            { text: '虚拟券商 (Broker)', link: '/guide/broker' },
            { text: '仓位算法 (Sizing)', link: '/guide/sizing' }
          ]
        },
        {
          text: '回测与分析',
          items: [
            { text: '回测引擎 (Backtest)', link: '/guide/backtest' },
            { text: '交互式 HTML 报告', link: '/guide/report' },
            { text: '常用分析工具 (Analysis)', link: '/guide/analysis' },
            { text: '避坑指南与最佳实践', link: '/guide/best-practices' }
          ]
        },
        {
          text: 'AI 协同',
          items: [
            { text: '🤖 AI Agent 技能 (zsrl/qka)', link: '/guide/agent-skill' }
          ]
        }
      ],
      '/api/': [
        {
          text: 'API 参考',
          items: [
            { text: 'API 概览与速查', link: '/api/' },
            { text: 'qka.Data', link: '/api/data' },
            { text: 'qka.Simulate', link: '/api/simulate' },
            { text: 'qka.Strategy', link: '/api/strategy' },
            { text: 'qka.Broker', link: '/api/broker' },
            { text: 'qka.SizingAccessor', link: '/api/sizing' },
            { text: 'qka.Backtest', link: '/api/backtest' },
            { text: 'qka.Analysis', link: '/api/analysis' }
          ]
        }
      ]
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/zsrl/qka' }
    ],

    search: {
      provider: 'local',
      options: {
        locales: {
          root: {
            translations: {
              button: {
                buttonText: '搜索文档',
                buttonAriaLabel: '搜索文档'
              },
              modal: {
                noResultsText: '无法找到相关结果',
                resetButtonTitle: '清除查询条件',
                footer: {
                  selectText: '选择',
                  navigateText: '切换',
                  closeText: '关闭'
                }
              }
            }
          }
        }
      }
    },

    footer: {
      message: '基于 MIT 协议开源',
      copyright: 'Copyright © 2024-present QKA Contributors'
    },

    docFooter: {
      prev: '上一篇',
      next: '下一篇'
    },

    outline: {
      label: '页面导航',
      level: [2, 3]
    },

    lastUpdated: {
      text: '最后更新于'
    }
  }
})
