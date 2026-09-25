'use strict'
//   node --test services/sandbox/tests/git_urls.test.js
const test = require('node:test')
const assert = require('node:assert/strict')

const { normalizeAzureUrl, redactCredentials } = require('../git_urls')

test('endereço antigo do Azure DevOps vira dev.azure.com', () => {
  assert.equal(
    normalizeAzureUrl('https://seller.visualstudio.com/Seller/_git/Linx.Services'),
    'https://dev.azure.com/seller/Seller/_git/Linx.Services',
  )
  assert.equal(
    normalizeAzureUrl('https://joao@seller.visualstudio.com/DefaultCollection/Seller/_git/Linx.Services'),
    'https://dev.azure.com/seller/Seller/_git/Linx.Services',
  )
})

test('outras URLs ficam como estão', () => {
  for (const url of [
    'https://dev.azure.com/seller/Seller/_git/SellerWeb',
    'https://linxpostos@dev.azure.com/linxpostos/linx-postos-smartpos/_git/Proteus',
    'https://github.com/cecon/CappyCloud.git',
  ]) {
    assert.equal(normalizeAzureUrl(url), url)
  }
})

test('mensagem de erro não leva credencial', () => {
  assert.equal(
    redactCredentials("fatal: could not read from 'https://pat:abc123@dev.azure.com/seller/x'"),
    "fatal: could not read from 'https://***@dev.azure.com/seller/x'",
  )
})
