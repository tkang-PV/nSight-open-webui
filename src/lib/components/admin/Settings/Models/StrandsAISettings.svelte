<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	export let saveHandler: Function;

	let loading = false;
	let config = {
		ENABLE_STRANDS_AI: true,
		AWS_PROFILE: '',
		AWS_REGION: '',
		MODEL_ID: '',
		CLICKHOUSE_MCP_BASE_URL: ''
	};

	// Export config getter for parent component to access
	export const getConfig = () => config;
	export const setConfig = (newConfig) => {
		console.log('[StrandsAISettings] setConfig called with:', newConfig);
		config = { ...config, ...newConfig };
		console.log('[StrandsAISettings] Config after setConfig:', config);
	};

	let internals = {
		tools: [],
		system_prompt: '',
		model_info: {},
		chain_of_thought: []
	};

	let showInternals = false;
	let healthStatus = null;
	let internalsLoading = false;
	let healthLoading = false;

	const loadConfigFromAPI = async () => {
		loading = true;
		try {
			const res = await fetch(`/api/v1/strands/config`, {
				method: 'GET',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${localStorage.token}`
				}
			});

			if (res.ok) {
				config = await res.json();
			} else {
				throw new Error('Failed to get Strands AI config');
			}
		} catch (error) {
			console.error('Error getting Strands AI config:', error);
			toast.error('Failed to get Strands AI configuration');
		}
		loading = false;
	};

	export const updateConfig = async () => {
		loading = true;
		try {
			const res = await fetch(`/api/v1/strands/config/update`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${localStorage.token}`
				},
				body: JSON.stringify(config)
			});

			if (res.ok) {
				const updatedConfig = await res.json();
				config = updatedConfig;
				toast.success('Strands AI configuration updated successfully');
				if (saveHandler) {
					saveHandler();
				}
			} else {
				throw new Error('Failed to update Strands AI config');
			}
		} catch (error) {
			console.error('Error updating Strands AI config:', error);
			toast.error('Failed to update Strands AI configuration');
		}
		loading = false;
	};

	const getInternals = async () => {
		internalsLoading = true;
		try {
			const res = await fetch(`/api/v1/strands/internals`, {
				method: 'GET',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${localStorage.token}`
				}
			});

			if (res.ok) {
				internals = await res.json();
				toast.success('Agent internals loaded successfully');
			} else {
				throw new Error('Failed to get agent internals');
			}
		} catch (error) {
			console.error('Error getting agent internals:', error);
			toast.error('Failed to get agent internals');
		} finally {
			internalsLoading = false;
		}
	};

	const checkHealth = async () => {
		healthLoading = true;
		healthStatus = null;
		try {
			const res = await fetch(`/api/v1/strands/health`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${localStorage.token}`
				},
				body: JSON.stringify({
					aws_profile: config.AWS_PROFILE,
					aws_region: config.AWS_REGION,
					model_id: config.MODEL_ID,
					clickhouse_mcp_base_url: config.CLICKHOUSE_MCP_BASE_URL
				})
			});

			if (res.ok) {
				healthStatus = await res.json();
				toast.success('Health check completed');
			} else {
				const errorData = await res.json().catch(() => ({ detail: 'Unknown error' }));
				healthStatus = { 
					status: 'error', 
					error: errorData.detail || `HTTP ${res.status}: ${res.statusText}`,
					agent: 'error',
					clickhouse: 'unknown'
				};
				toast.error(`Health check failed: ${errorData.detail || res.statusText}`);
			}
		} catch (error) {
			console.error('Error checking health:', error);
			healthStatus = { 
				status: 'error', 
				error: error.message,
				agent: 'error',
				clickhouse: 'unknown'
			};
			toast.error(`Failed to check health: ${error.message}`);
		} finally {
			healthLoading = false;
		}
	};

	const testTool = async (toolName: string, args: any = {}) => {
		try {
			const res = await fetch(`/api/v1/strands/tools/test`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${localStorage.token}`
				},
				body: JSON.stringify({
					tool_name: toolName,
					args: args
				})
			});

			if (res.ok) {
				const result = await res.json();
			const resultFull = typeof result === 'string' ? result : JSON.stringify(result);
			const resultStr = resultFull.length > 200 ? resultFull.substring(0, 200) + '...' : resultFull;
				toast.success(`${toolName}: ${resultStr}`);
				console.log('Tool result:', result);
			} else {
				const errorData = await res.json().catch(() => ({ detail: 'Unknown error' }));
				toast.error(`Failed to test tool ${toolName}: ${errorData.detail || res.statusText}`);
			}
		} catch (error) {
			console.error(`Error testing tool ${toolName}:`, error);
			toast.error(`Failed to test tool ${toolName}: ${error.message}`);
		}
	};

	onMount(async () => {
		await loadConfigFromAPI();
		// Wait for config to be loaded before checking health
		checkHealth();
	});
</script>

<div class="space-y-3 text-sm">
	<div>
		<div class="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
			{$i18n.t('Strands AI Configuration')}
		</div>

		<div class="space-y-3">
			<!-- Health Status -->
			<div class="flex items-center justify-between">
				<div class="text-xs font-medium">Health Status</div>
				<button
					type="button"
					class="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
					on:click={checkHealth}
					disabled={healthLoading}
				>
					{healthLoading ? 'Checking...' : 'Check Health'}
				</button>
			</div>

			{#if healthStatus}
				<div class="p-3 rounded-lg border {healthStatus.status === 'ok' ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800' : healthStatus.status === 'degraded' ? 'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800' : 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'}">
					<div class="text-xs space-y-1">
						<div><strong>Status:</strong> {healthStatus.status}</div>
						<div><strong>Agent:</strong> {healthStatus.agent || 'unknown'} {healthStatus.agent_error ? `(${healthStatus.agent_error})` : ''}</div>
						<div><strong>ClickHouse:</strong> {healthStatus.clickhouse || 'unknown'} {healthStatus.clickhouse_error ? `(${healthStatus.clickhouse_error})` : ''}</div>
						{#if healthStatus.error}
							<div class="text-red-600 dark:text-red-400"><strong>Error:</strong> {healthStatus.error}</div>
						{/if}
					</div>
				</div>
			{/if}

			<!-- AWS Configuration -->
			<div>
				<div class="mb-2 text-xs font-medium">AWS Profile</div>
				<input
					class="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-none"
					placeholder="AWS Profile (e.g., nSightS3Profile)"
					bind:value={config.AWS_PROFILE}
					disabled={loading}
				/>
			</div>

			<div>
				<div class="mb-2 text-xs font-medium">AWS Region</div>
				<input
					class="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-none"
					placeholder="AWS Region (e.g., us-west-2)"
					bind:value={config.AWS_REGION}
					disabled={loading}
				/>
			</div>

			<div>
				<div class="mb-2 text-xs font-medium">Bedrock Model ID</div>
				<input
					class="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-none"
					placeholder="Bedrock Model ID"
					bind:value={config.MODEL_ID}
					disabled={loading}
				/>
			</div>

			<div>
				<div class="mb-2 text-xs font-medium">ClickHouse MCP Base URL</div>
				<input
					class="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-none"
					placeholder="ClickHouse MCP Base URL"
					bind:value={config.CLICKHOUSE_MCP_BASE_URL}
					disabled={loading}
				/>
			</div>

			<!-- Agent Internals -->
			<div class="flex items-center justify-between">
				<div class="text-xs font-medium">Agent Internals</div>
				<button
					type="button"
					class="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
					on:click={async () => {
						if (!showInternals) {
							await getInternals();
						}
						showInternals = !showInternals;
					}}
					disabled={internalsLoading}
				>
					{internalsLoading ? 'Loading...' : showInternals ? 'Hide' : 'Show'} Internals
				</button>
			</div>

			{#if showInternals}
				<div class="space-y-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800">
					<!-- Tools -->
					<div>
						<div class="mb-2 text-xs font-medium">Available Tools</div>
						<div class="space-y-2">
							{#each internals.tools as tool}
								<div class="p-2 rounded border bg-white dark:bg-gray-700">
									<div class="flex items-center justify-between">
										<div class="font-medium text-xs">{tool.name}</div>
										<button
											type="button"
											class="px-2 py-1 text-xs bg-blue-100 hover:bg-blue-200 dark:bg-blue-900 dark:hover:bg-blue-800 rounded transition"
											on:click={(e) => {
												e.preventDefault();
												e.stopPropagation();
												let args = {};
												if (tool.name === 'list_tables') {
													args = { database: 'nSight_all' };
												} else if (tool.name === 'run_select_query') {
													args = { query: 'SELECT version();' };
												}
												testTool(tool.name, args);
											}}
										>
											Test
										</button>
									</div>
									{#if tool.description}
										<div class="text-xs text-gray-600 dark:text-gray-400 mt-1">
											{tool.description}
										</div>
									{/if}
								</div>
							{/each}
						</div>
					</div>

					<!-- Model Info -->
					<div>
						<div class="mb-2 text-xs font-medium">Model Information</div>
						<div class="p-2 rounded border bg-white dark:bg-gray-700">
							<pre class="text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{JSON.stringify(internals.model_info, null, 2)}</pre>
						</div>
					</div>

					<!-- Chain of Thought -->
					{#if internals.chain_of_thought && internals.chain_of_thought.length > 0}
						<div>
							<div class="mb-2 text-xs font-medium">Chain of Thought</div>
							<div class="space-y-2">
								{#each internals.chain_of_thought as thought}
									<div class="p-2 rounded border bg-white dark:bg-gray-700">
										<pre class="text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{JSON.stringify(thought, null, 2)}</pre>
									</div>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	pre {
		font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
		font-size: 11px;
		line-height: 1.4;
	}
</style>
