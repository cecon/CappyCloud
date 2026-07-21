function cappycloudPayloadDiagnostic(
  req: any,
  previousMessages: any[],
  tools: any[],
  commands: any[],
) {
  const categories: CappycloudDiagnosticCategory[] = []
  cappycloudAddDiagnosticCategory(categories, 'user_message', cappycloudByteLength(req.message))
  cappycloudAddDiagnosticCategory(categories, 'conversation_history', cappycloudByteLength(previousMessages))
  cappycloudAddDiagnosticCategory(
    categories,
    'attachments',
    Array.isArray(req.attachments)
      ? req.attachments.reduce((sum: number, attachment: any) => {
          return sum + cappycloudByteLength(attachment?.data) + cappycloudByteLength(attachment?.mime_type)
        }, 0)
      : 0,
  )
  const builtinToolBytes = tools
    .filter(tool => !tool?.isMcp)
    .reduce((sum, tool) => sum + cappycloudToolSchemaSize(tool), 0)
  const mcpToolBytes = tools
    .filter(tool => tool?.isMcp)
    .reduce((sum, tool) => sum + cappycloudToolSchemaSize(tool), 0)
  cappycloudAddDiagnosticCategory(categories, 'tool_schemas', builtinToolBytes)
  cappycloudAddDiagnosticCategory(
    categories,
    'mcp_tool_schemas',
    mcpToolBytes + cappycloudByteLength(commands.map(command => command?.name ?? command)),
  )
  cappycloudAddDiagnosticCategory(
    categories,
    'runtime_context',
    cappycloudByteLength({
      model: req.model,
      provider_base_url: req.provider_base_url ? 'configured' : '',
      provider_api_format: req.provider_api_format,
      session_id: req.session_id,
    }),
  )

  categories.sort((a, b) => b.size_bytes - a.size_bytes)
  const totalSizeBytes = categories.reduce((sum, category) => sum + category.size_bytes, 0)
  for (const category of categories) {
    category.percentage = totalSizeBytes > 0 ? Math.round((category.size_bytes / totalSizeBytes) * 1000) / 10 : 0
  }
  return {
    total_size_bytes: totalSizeBytes,
    source: 'openclaude',
    generated_at: new Date().toISOString(),
    categories,
  }
}
