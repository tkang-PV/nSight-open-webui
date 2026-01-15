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

	let internals = {
		tools: [],
		system_prompt: '',
		model_info: {},
		chain_of_thought: []
	};

	let showInternals = false;
	let healthStatus = null;

	const getConfig = async () => {
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

	const updateConfig = async () => {
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
			} else {
				throw new Error('Failed to get agent internals');
			}
		} catch (error) {
			console.error('Error getting agent internals:', error);
			toast.error('Failed to get agent internals');
		}
	};

	const checkHealth = async () => {
		try {
			const res = await fetch(`/api/v1/strands/health`, {
				method: 'GET',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${localStorage.token}`
				}
			});

			if (res.ok) {
				healthStatus = await res.json();
			} else {
				throw new Error('Failed to check health');
			}
		} catch (error) {
			console.error('Error checking health:', error);
			healthStatus = { status: 'error', error: error.message };
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
				toast.success(`Tool ${toolName} executed successfully`);
				console.log('Tool result:', result);
			} else {
				throw new Error(`Failed to test tool ${toolName}`);
			}
		} catch (error) {
			console.error(`Error testing tool ${toolName}:`, error);
			toast.error(`Failed to test tool ${toolName}`);
		}
	};

	onMount(() => {
		getConfig();
		checkHealth();
	});
</script>

<div class="flex flex-col h-full justify-between space-y-3 text-sm">
	<div class="space-y-3">
		<div>
			<div class="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
				{$i18n.t('Strands AI Configuration')}
			</div>

			<div class="space-y-3">
				<!-- Health Status -->
				<div class="flex items-center justify-between">
					<div class="text-xs font-medium">Health Status</div>
					<button
						class="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 rounded-lg transition"
						on:click={checkHealth}
					>
						Check Health
					</button>
				</div>

				{#if healthStatus}
					<div class="p-3 rounded-lg border {healthStatus.status === 'ok' ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800' : 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'}">
						<div class="text-xs">
							<div><strong>Status:</strong> {healthStatus.status}</div>
							<div><strong>Agent:</strong> {healthStatus.agent || 'unknown'}</div>
							<div><strong>ClickHouse:</strong> {healthStatus.clickhouse || 'unknown'}</div>
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
						class="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 rounded-lg transition"
						on:click={() => {
							showInternals = !showInternals;
							if (showInternals) {
								getInternals();
							}
						}}
					>
						{showInternals ? 'Hide' : 'Show'} Internals
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
												class="px-2 py-1 text-xs bg-blue-100 hover:bg-blue-200 dark:bg-blue-900 dark:hover:bg-blue-800 rounded transition"
												on:click={() => {
													// Add default parameters for tools that require them
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

	<div class="flex justify-end pt-3">
		<button
			class="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-gray-100 transition rounded-lg text-sm"
			on:click={updateConfig}
			disabled={loading}
		>
			{loading ? 'Saving...' : 'Save'}
		</button>
	</div>
</div>

<style>
	pre {
		font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
		font-size: 11px;
		line-height: 1.4;
	}
</style>
