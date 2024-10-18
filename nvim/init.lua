local vim = vim
local Plug = vim.fn['plug#']

-- Plugins
vim.call('plug#begin')

Plug('neovim/nvim-lspconfig') -- LSP
Plug('nvim-treesitter/nvim-treesitter') -- Code navigation
Plug('ray-x/guihua.lua', {['do'] = 'cd lua/fzy && make' })
Plug('ray-x/navigator.lua')
Plug('hrsh7th/cmp-nvim-lsp') -- Completion
Plug('hrsh7th/cmp-buffer')
Plug('hrsh7th/cmp-path')
Plug('hrsh7th/cmp-cmdline')
Plug('hrsh7th/nvim-cmp')
Plug('hrsh7th/cmp-vsnip')
Plug('hrsh7th/vim-vsnip')
Plug('ray-x/go.nvim') -- Go
Plug('mfussenegger/nvim-dap') -- DAP
Plug('leoluz/nvim-dap-go') -- Go Debug Adapter (requires Delve debugger)
Plug('nvim-neotest/nvim-nio')
Plug('rcarriga/nvim-dap-ui')
Plug('nvim-lua/plenary.nvim') -- Fuzzy finder
Plug('nvim-telescope/telescope.nvim', { ['tag'] = '0.1.8' })
Plug('BurntSushi/ripgrep')
Plug('nvim-telescope/telescope-fzf-native.nvim', {['do'] = 'make' })
Plug('ray-x/aurora') -- Theme

vim.call('plug#end')

-- Navigator
require'navigator'.setup()

-- Set up nvim-cmp.
local cmp = require'cmp'

cmp.setup({
  snippet = {
    -- REQUIRED - you must specify a snippet engine
    expand = function(args)
      vim.fn["vsnip#anonymous"](args.body) -- For `vsnip` users.
      -- vim.snippet.expand(args.body) -- For native neovim snippets (Neovim v0.10+)
    end,
  },
  window = {
    -- completion = cmp.config.window.bordered(),
    -- documentation = cmp.config.window.bordered(),
  },
  mapping = cmp.mapping.preset.insert({
    ['<C-b>'] = cmp.mapping.scroll_docs(-4),
    ['<C-f>'] = cmp.mapping.scroll_docs(4),
    ['<C-Space>'] = cmp.mapping.complete(),
    ['<C-e>'] = cmp.mapping.abort(),
    ['<CR>'] = cmp.mapping.confirm({ select = true }), -- Accept currently selected item. Set `select` to `false` to only confirm explicitly selected items.
  }),
  sources = cmp.config.sources({
    { name = 'nvim_lsp' },
    { name = 'vsnip' }, -- For vsnip users.
  }, {
    { name = 'buffer' },
  })
})

-- To use git you need to install the plugin petertriho/cmp-git and uncomment lines below
-- Set configuration for specific filetype.
--[[ cmp.setup.filetype('gitcommit', {
  sources = cmp.config.sources({
    { name = 'git' },
  }, {
    { name = 'buffer' },
  })
)
require("cmp_git").setup() ]]-- 

-- Use buffer source for `/` and `?` (if you enabled `native_menu`, this won't work anymore).
cmp.setup.cmdline({ '/', '?' }, {
  mapping = cmp.mapping.preset.cmdline(),
  sources = {
    { name = 'buffer' }
  }
})

-- Use cmdline & path source for ':' (if you enabled `native_menu`, this won't work anymore).
cmp.setup.cmdline(':', {
  mapping = cmp.mapping.preset.cmdline(),
  sources = cmp.config.sources({
    { name = 'path' }
  }, {
    { name = 'cmdline' }
  }),
  matching = { disallow_symbol_nonprefix_matching = false }
})

-- Set up lspconfig.
local capabilities = require('cmp_nvim_lsp').default_capabilities()
require('lspconfig')['gopls'].setup {
  capabilities = capabilities
}

-- Go plugin setup
require('go').setup()

-- Run goimports and gofmt on save
local format_sync_grp = vim.api.nvim_create_augroup("goimports", {})
vim.api.nvim_create_autocmd("BufWritePre", {
  pattern = "*.go",
  callback = function()
   require('go.format').goimports()
  end,
  group = format_sync_grp,
})

-- DAP
local dap = require("dap")
dap.adapters.delve = {
  type = 'server',
  port = '${port}',
  executable = {
    command = 'dlv',
    args = {'dap', '-l', '127.0.0.1:${port}'},
  }
}
require("dap-go").setup({
    dap_configurations = {
        {
            type = "go",
            name = "Debug (Build Flags & Arguments)",
            request = "launch",
            --program = "${file}",
            program = "./${relativeFileDirname}",
            args = require("dap-go").get_arguments,
            buildFlags = require("dap-go").get_build_flags,
        },
    }
})
require("dapui").setup()

-- Fuzzy finder
require('telescope').setup()
require('telescope').load_extension('fzf')
local builtin = require('telescope.builtin')
vim.keymap.set('n', '<leader>ff', builtin.find_files, {})
vim.keymap.set('n', '<leader>fg', builtin.live_grep, {})
vim.keymap.set('n', '<leader>fb', builtin.buffers, {})
vim.keymap.set('n', '<leader>fh', builtin.help_tags, {})

-- Color scheme
vim.cmd [[colorscheme vim]]
vim.cmd [[set nu rnu]]
