local vim = vim

-- Color scheme
vim.cmd [[set nu rnu]]

-- Plugins
local Plug = vim.fn['plug#']

vim.call('plug#begin')
Plug('ray-x/go.nvim') -- Go
Plug('hrsh7th/vim-vsnip') -- Snippet engine
Plug('hrsh7th/cmp-nvim-lsp') -- Completion
Plug('hrsh7th/cmp-buffer')
Plug('hrsh7th/cmp-path')
Plug('hrsh7th/cmp-cmdline')
Plug('hrsh7th/nvim-cmp')
Plug('hrsh7th/cmp-vsnip') -- Completion with snippet 
Plug('ellisonleao/gruvbox.nvim') -- Colorscheme
Plug('nvim-lua/plenary.nvim')
Plug('nvim-telescope/telescope.nvim')
Plug('danobi/prr', {rtp = 'vim'})
vim.call('plug#end')


-- Language Servers
local lspconfig = require("lspconfig")

-- Terraform Language Server
lspconfig.terraformls.setup{}
vim.api.nvim_create_autocmd({"BufWritePre"}, {
  pattern = {"*.tf", "*.tfvars"},
  callback = function()
    vim.lsp.buf.format()
  end,
})

-- Go Language Server
lspconfig.gopls.setup({})

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

-- Completion
local cmp = require'cmp'
cmp.setup({
  snippet = {
    -- REQUIRED
    expand = function(args)
      vim.fn["vsnip#anonymous"](args.body) -- For `vsnip` users.
      vim.snippet.expand(args.body) -- For native neovim snippets (Neovim v0.10+)
    end,
  },
  window = {},
  mapping = cmp.mapping.preset.insert({
    ['<C-b>'] = cmp.mapping.scroll_docs(-4),
    ['<C-f>'] = cmp.mapping.scroll_docs(4),
    ['<C-Space>'] = cmp.mapping.complete(),
    ['<C-e>'] = cmp.mapping.abort(),
    ['<tab>'] = cmp.mapping.confirm({ select = true }), -- Accept currently selected item. Set `select` to `false` to only confirm explicitly selected items.
  }),
  sources = cmp.config.sources({
    { name = 'nvim_lsp' },
    { name = 'vsnip' },
  }, {
    { name = 'buffer' },
  })
})
-- Use buffer source for `/` and `?` (if you enabled `native_menu`, this won't work anymore).
cmp.setup.cmdline({ '/', '?' }, {
  mapping = cmp.mapping.preset.cmdline(),
  sources = {
    { name = 'buffer' }
  }
})


vim.cmd [[set mouse=]]

--- Colorscheme
vim.o.background = "dark" -- or "light" for light mode
vim.cmd([[colorscheme gruvbox]])

--- Telescope
local builtin = require('telescope.builtin')
vim.keymap.set('n', '<leader><leader>', builtin.find_files, { desc = 'Telescope find files' })
vim.keymap.set('n', '<leader>fg', builtin.live_grep, { desc = 'Telescope live grep' })
vim.keymap.set('n', '<leader>fb', builtin.buffers, { desc = 'Telescope buffers' })
vim.keymap.set('n', '<leader>fh', builtin.help_tags, { desc = 'Telescope help tags' })

--- PRR
-- Automatically set up highlighting for `.prr` review files
-- Use `:hi` to see the various definitions we kinda abuse here
local augroup = vim.api.nvim_create_augroup("Prr", { clear = true })

vim.api.nvim_create_autocmd({ "BufRead", "BufNewFile" }, {
  group = augroup,
  pattern = "*.prr",
  callback = function()
    vim.cmd("set syntax=on")

    -- Make prr added/deleted highlighting more apparent
    vim.cmd("hi! link prrAdded Function")
    vim.cmd("hi! link prrRemoved Keyword")
    vim.cmd("hi! link prrFile Special")

    -- Make file delimiters more apparent
    vim.cmd("hi! link prrHeader Directory")

    -- Reduce all the noise from color
    vim.cmd("hi! link prrIndex Special")
    vim.cmd("hi! link prrChunk Special")
    vim.cmd("hi! link prrChunkH Special")
    vim.cmd("hi! link prrTagName Special")
    vim.cmd("hi! link prrResult Special")
  end,
})
