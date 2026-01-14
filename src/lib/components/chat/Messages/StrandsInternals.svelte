<script lang="ts">
	import { createEventDispatcher, getContext, tick } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';
	import TextareaWithLineNumbers from '$lib/components/common/TextareaWithLineNumbers.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher();

	export let internals: any = null;
	export let expanded: boolean = true; // Expand by default to show thinking process
	export let streaming: boolean = false; // Show if currently streaming

	let activeTab: 'overview' | 'tools' | 'thinking' | 'timeline' | 'dbqueries' = 'thinking';
	let systemPromptTab: 'prompt' | 'preview' = 'preview';
	let systemInstructionsExpanded: boolean = false; // Collapsed by default
	let rawDataExpanded: boolean = false; // Collapsed by default
	let previewContentElement: HTMLDivElement;
	let previewLineNumbersElement: HTMLDivElement;
	let promptTextareaElement: any;
	let sharedScrollPosition = 0;

	// Debug logging
	console.log('StrandsInternals component mounted with internals:', internals);
	
	$: if (internals) {
		console.log('Strands AI Thinking Process:', internals);
		console.log('Internals keys:', Object.keys(internals));
		console.log('Has chain_of_thought:', internals.chain_of_thought);
		console.log('Has tools:', internals.tools);
		console.log('Has execution_log:', internals.execution_log);
		if (internals.execution_log) {
			console.log('Execution log length:', internals.execution_log.length);
			console.log('Execution log sample:', internals.execution_log.slice(0, 3));
		}
	} else {
		console.log('StrandsInternals: No internals data received');
	}

	const toggleExpanded = () => {
		expanded = !expanded;
	};

	const formatJson = (obj: any) => {
		return JSON.stringify(obj, null, 2);
	};

	const formatTimestamp = (timestamp: string) => {
		if (!timestamp) return '';
		const date = new Date(timestamp);
		return date.toLocaleTimeString();
	};

	const getToolIcon = (toolName: string) => {
		if (toolName.includes('database') || toolName.includes('query')) return '🗄️';
		if (toolName.includes('search')) return '🔍';
		if (toolName.includes('list')) return '📋';
		if (toolName.includes('run')) return '▶️';
		return '🔧';
	};

	const getToolExecutionTime = (tool: any) => {
		if (tool.execution_time) return `${tool.execution_time}ms`;
		if (tool.start_time && tool.end_time) {
			const start = new Date(tool.start_time).getTime();
			const end = new Date(tool.end_time).getTime();
			return `${end - start}ms`;
		}
		return null;
	};

	const syncPreviewScroll = () => {
		if (previewContentElement && previewLineNumbersElement) {
			previewLineNumbersElement.scrollTop = previewContentElement.scrollTop;
			sharedScrollPosition = previewContentElement.scrollTop;
		}
	};

	const handlePromptScrollChange = (scrollTop: number) => {
		sharedScrollPosition = scrollTop;
	};

	const handleSystemPromptTabSwitch = async (newTab: 'prompt' | 'preview') => {
		if (systemPromptTab === 'preview' && previewContentElement) {
			sharedScrollPosition = previewContentElement.scrollTop;
		} else if (systemPromptTab === 'prompt' && promptTextareaElement) {
			sharedScrollPosition = promptTextareaElement.getScrollTop();
		}
		
		systemPromptTab = newTab;
		
		await tick();
		
		const applyScrollPosition = () => {
			if (newTab === 'prompt' && promptTextareaElement) {
				promptTextareaElement.setScrollTop(sharedScrollPosition);
			} else if (newTab === 'preview' && previewContentElement) {
				previewContentElement.scrollTop = sharedScrollPosition;
				if (previewLineNumbersElement) {
					previewLineNumbersElement.scrollTop = sharedScrollPosition;
				}
			}
		};
		
		applyScrollPosition();
		
		setTimeout(applyScrollPosition, 10);
		setTimeout(applyScrollPosition, 50);
	};

	// Reactive size metrics for system prompt
	$: systemCharCount = internals?.system_prompt?.length || 0;
	$: systemByteCount = new TextEncoder().encode(internals?.system_prompt || '').length;
</script>

{#if internals}
	<div class="strands-internals mt-3 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden shadow-sm">
		<!-- Header -->
		<button
			class="w-full px-4 py-3 bg-gradient-to-r from-blue-50 via-indigo-50 to-purple-50 dark:from-blue-900/20 dark:via-indigo-900/20 dark:to-purple-900/20 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between hover:from-blue-100 hover:via-indigo-100 hover:to-purple-100 dark:hover:from-blue-900/30 dark:hover:via-indigo-900/30 dark:hover:to-purple-900/30 transition-all duration-200"
			on:click={toggleExpanded}
		>
			<div class="flex items-center space-x-3">
				<div class="relative">
					<div class="w-3 h-3 bg-blue-500 rounded-full {streaming ? 'animate-pulse' : ''}"></div>
					{#if streaming}
						<div class="absolute inset-0 w-3 h-3 bg-blue-500 rounded-full animate-ping"></div>
					{/if}
				</div>
				<div class="flex flex-col items-start">
					<span class="font-semibold text-sm text-gray-800 dark:text-gray-200">
						🧠 {$i18n.t('Agent Thinking Process')}
					</span>
					{#if streaming}
						<span class="text-xs text-blue-600 dark:text-blue-400 mt-0.5">
							{$i18n.t('Analyzing in progress...')}
						</span>
					{/if}
				</div>
			</div>
			<div class="flex items-center space-x-2">
				{#if internals.tools && internals.tools.length > 0}
					<span class="text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-2 py-1 rounded-full">
						{internals.tools.length} {$i18n.t('tools')}
					</span>
				{/if}
				<svg
					class="w-5 h-5 text-gray-500 transition-transform duration-200 {expanded ? 'rotate-180' : ''}"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
				</svg>
			</div>
		</button>

		{#if expanded}
			<div class="bg-white dark:bg-gray-800">
				<!-- Tab Navigation -->
				<div class="flex border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
					<button
						class="px-4 py-2 text-sm font-medium transition-colors {activeTab === 'thinking' ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 bg-white dark:bg-gray-800' : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'}"
						on:click={() => activeTab = 'thinking'}
					>
						💭 {$i18n.t('Thinking Steps')}
					</button>
					<button
						class="px-4 py-2 text-sm font-medium transition-colors {activeTab === 'dbqueries' ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 bg-white dark:bg-gray-800' : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'}"
						on:click={() => activeTab = 'dbqueries'}
					>
						🗄️ {$i18n.t('DB Queries')}
					</button>
					<button
						class="px-4 py-2 text-sm font-medium transition-colors {activeTab === 'timeline' ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 bg-white dark:bg-gray-800' : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'}"
						on:click={() => activeTab = 'timeline'}
					>
						⏱️ {$i18n.t('Timeline')}
					</button>
					<button
						class="px-4 py-2 text-sm font-medium transition-colors {activeTab === 'overview' ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 bg-white dark:bg-gray-800' : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'}"
						on:click={() => activeTab = 'overview'}
					>
						ℹ️ {$i18n.t('Overview')}
					</button>
				</div>

				<!-- Tab Content -->
				<div class="p-4">
					<!-- Thinking Steps Tab -->
					{#if activeTab === 'thinking'}
						<div class="space-y-3">
							{#if internals.chain_of_thought && internals.chain_of_thought.length > 0}
								{@const reasoningSteps = internals.chain_of_thought.filter(step => {
									// Only show actual agent reasoning, filter out tool calls and technical steps
									if (!step.description && !step.reasoning_text && !step.reasoning) return false;
									
									const description = step.description || '';
									const reasoning = step.reasoning_text || step.reasoning || '';
									
									// Filter out tool-related steps
									if (description.includes('Calling tool:') || 
										description.includes('Tool ') || 
										description.includes('Using ') ||
										description.includes('Step ') ||
										description.includes('completed successfully') ||
										description.includes('failed')) {
										return false;
									}
									
									// Only include steps that contain actual reasoning text
									return (description.includes('Agent reasoning') || 
											reasoning.length > 0 || 
											(description.length > 0 && !description.includes('tool') && !description.includes('Tool')));
								})}
								{#if reasoningSteps.length > 0}
									<div class="mb-4">
										<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center">
											<span class="text-lg mr-2">🧠</span>
											{$i18n.t('Reasoning Process')}
										</h4>
										<div class="space-y-3">
											{#each reasoningSteps as step, index}
												<div class="relative pl-8 pb-4 border-l-2 border-blue-300 dark:border-blue-600 last:border-l-0 last:pb-0">
													<!-- Timeline dot -->
													<div class="absolute left-0 top-0 -translate-x-1/2 w-4 h-4 rounded-full bg-blue-500 border-2 border-white dark:border-gray-800 shadow-sm"></div>
													
													<!-- Step content -->
													<div class="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-lg p-3 shadow-sm">
														<div class="flex items-center justify-between mb-2">
															<span class="text-xs font-bold text-blue-700 dark:text-blue-300 uppercase tracking-wide">
																Reasoning {index + 1}
															</span>
															{#if step.timestamp}
																<span class="text-xs text-gray-500 dark:text-gray-400">
																	{formatTimestamp(step.timestamp)}
																</span>
															{/if}
														</div>
														<div class="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">
															{step.reasoning_text || step.reasoning || step.description?.replace('Agent reasoning: ', '') || step.content || step.thought}
														</div>
													</div>
												</div>
											{/each}
										</div>
									</div>
								{:else}
									<div class="text-center py-8 text-gray-500 dark:text-gray-400">
										<div class="text-4xl mb-2">🤔</div>
										<p class="text-sm">{$i18n.t('No agent reasoning recorded')}</p>
										<p class="text-xs mt-1">{$i18n.t('The agent processed this request without explicit reasoning steps')}</p>
									</div>
								{/if}
							{:else}
								<div class="text-center py-8 text-gray-500 dark:text-gray-400">
									<div class="text-4xl mb-2">🤔</div>
									<p class="text-sm">{$i18n.t('No thinking steps recorded')}</p>
									<p class="text-xs mt-1">{$i18n.t('The agent processed this request directly')}</p>
								</div>
							{/if}
						</div>
					{/if}

					<!-- DB Queries Tab -->
					{#if activeTab === 'dbqueries'}
						{@const dbQueries = internals.execution_log?.filter(event => 
							event.type === 'clickhouse_query'
						) || []}
						<div class="space-y-3">
							{#if dbQueries.length > 0}
								<div class="mb-4">
									<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center">
										<span class="text-lg mr-2">🗄️</span>
										{$i18n.t('Database Queries')} ({dbQueries.length})
									</h4>
									<div class="space-y-3">
										{#each dbQueries as queryEvent, index}
											<div class="relative pl-8 pb-4 border-l-2 border-cyan-300 dark:border-cyan-600 last:border-l-0 last:pb-0">
												<!-- Timeline dot -->
												<div class="absolute left-0 top-0 -translate-x-1/2 w-4 h-4 rounded-full bg-cyan-500 border-2 border-white dark:border-gray-800 shadow-sm"></div>
												
												<!-- Query content -->
												<div class="bg-gradient-to-r from-cyan-50 to-blue-50 dark:from-cyan-900/20 dark:to-blue-900/20 rounded-lg p-3 shadow-sm">
													<div class="flex items-center justify-between mb-2">
														<span class="text-xs font-bold text-cyan-700 dark:text-cyan-300 uppercase tracking-wide">
															ClickHouse Query {index + 1}
														</span>
														{#if queryEvent.timestamp}
															<span class="text-xs text-gray-500 dark:text-gray-400">
																{formatTimestamp(queryEvent.timestamp)}
															</span>
														{/if}
													</div>
													<div class="bg-gray-900 dark:bg-black rounded p-3 overflow-x-auto">
														<pre class="text-xs text-green-400 dark:text-green-300 font-mono leading-relaxed whitespace-pre-wrap">{queryEvent.query}</pre>
													</div>
												</div>
											</div>
										{/each}
									</div>
								</div>
							{:else}
								<div class="text-center py-8 text-gray-500 dark:text-gray-400">
									<div class="text-4xl mb-2">🗄️</div>
									<p class="text-sm">{$i18n.t('No database queries recorded')}</p>
									<p class="text-xs mt-1">{$i18n.t('No ClickHouse queries were executed in this execution log')}</p>
								</div>
							{/if}
						</div>
					{/if}

					<!-- Timeline Tab -->
					{#if activeTab === 'timeline'}
						<div class="space-y-3">
							<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center">
								<span class="text-lg mr-2">⏱️</span>
								{$i18n.t('Execution Timeline')}
							</h4>
							
							{#if internals.execution_log && internals.execution_log.length > 0}
								<div class="relative">
									<!-- Timeline line -->
									<div class="absolute left-6 top-0 bottom-0 w-0.5 bg-gradient-to-b from-purple-300 via-blue-300 to-green-300 dark:from-purple-700 dark:via-blue-700 dark:to-green-700"></div>
									
									<!-- Timeline events -->
									<div class="space-y-4">
										{#each internals.execution_log as event, index}
											<div class="relative pl-14">
												<!-- Event marker -->
												<div class="absolute left-3 top-2 w-6 h-6 rounded-full bg-gradient-to-br {
													event.type === 'tool_call' ? 'from-green-400 to-emerald-500' :
													event.type === 'thought' ? 'from-blue-400 to-indigo-500' :
													event.type === 'error' ? 'from-red-400 to-pink-500' :
													'from-purple-400 to-violet-500'
												} border-2 border-white dark:border-gray-800 shadow-lg flex items-center justify-center text-white text-xs font-bold">
													{index + 1}
												</div>
												
												<!-- Event content -->
												<div class="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 shadow-sm">
													<div class="flex items-center justify-between mb-2">
														<span class="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
															{event.type || 'Event'}
														</span>
														{#if event.timestamp}
															<span class="text-xs text-gray-500 dark:text-gray-400">
																{formatTimestamp(event.timestamp)}
															</span>
														{/if}
													</div>
													<div class="text-sm text-gray-800 dark:text-gray-200">
														{event.description || event.message || JSON.stringify(event)}
													</div>
													{#if event.duration}
														<div class="mt-2 text-xs text-gray-500 dark:text-gray-400">
															⏱️ Duration: {event.duration}ms
														</div>
													{/if}
												</div>
											</div>
										{/each}
									</div>
								</div>
							{:else}
								<div class="text-center py-8 text-gray-500 dark:text-gray-400">
									<div class="text-4xl mb-2">📊</div>
									<p class="text-sm">{$i18n.t('No timeline data available')}</p>
									<p class="text-xs mt-1">{$i18n.t('Execution log not recorded')}</p>
								</div>
							{/if}
						</div>
					{/if}

					<!-- Overview Tab -->
					{#if activeTab === 'overview'}
						<div class="space-y-4">
							<!-- Model Information -->
							{#if internals.model_info}
								<div>
									<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center">
										<svg class="w-4 h-4 mr-2 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
										</svg>
										{$i18n.t('Model Configuration')}
									</h4>
									<div class="bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-lg p-4 border border-purple-200 dark:border-purple-800">
										<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
											<div class="flex items-start space-x-2">
												<span class="text-gray-600 dark:text-gray-400 text-sm">🤖 Model:</span>
												<span class="font-mono text-sm text-purple-700 dark:text-purple-300 font-semibold">
													{internals.model_info.model_id}
												</span>
											</div>
											<div class="flex items-start space-x-2">
												<span class="text-gray-600 dark:text-gray-400 text-sm">🌍 Region:</span>
												<span class="font-mono text-sm text-gray-700 dark:text-gray-300">
													{internals.model_info.aws_region}
												</span>
											</div>
											<div class="flex items-start space-x-2">
												<span class="text-gray-600 dark:text-gray-400 text-sm">👤 Profile:</span>
												<span class="font-mono text-sm text-gray-700 dark:text-gray-300">
													{internals.model_info.aws_profile}
												</span>
											</div>
											<div class="flex items-start space-x-2">
												<span class="text-gray-600 dark:text-gray-400 text-sm">📊 Max Tokens:</span>
												<span class="font-mono text-sm text-gray-700 dark:text-gray-300">
													{internals.model_info.max_tokens}
												</span>
											</div>
										</div>
									</div>
								</div>
							{/if}

							<!-- Performance Metrics -->
							{#if internals.metrics}
								<div>
									<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center">
										<span class="text-lg mr-2">📈</span>
										{$i18n.t('Performance Metrics')}
									</h4>
									<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
										{#if internals.metrics.total_tokens}
											<div class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 border border-blue-200 dark:border-blue-800">
												<div class="text-xs text-gray-600 dark:text-gray-400 mb-1">Total Tokens</div>
												<div class="text-lg font-bold text-blue-700 dark:text-blue-300">
													{internals.metrics.total_tokens}
												</div>
											</div>
										{/if}
										{#if internals.metrics.execution_time}
											<div class="bg-green-50 dark:bg-green-900/20 rounded-lg p-3 border border-green-200 dark:border-green-800">
												<div class="text-xs text-gray-600 dark:text-gray-400 mb-1">Execution Time</div>
												<div class="text-lg font-bold text-green-700 dark:text-green-300">
													{internals.metrics.execution_time}s
												</div>
											</div>
										{/if}
										{#if internals.metrics.tool_calls}
											<div class="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3 border border-purple-200 dark:border-purple-800">
												<div class="text-xs text-gray-600 dark:text-gray-400 mb-1">Tool Calls</div>
												<div class="text-lg font-bold text-purple-700 dark:text-purple-300">
													{internals.metrics.tool_calls}
												</div>
											</div>
										{/if}
										{#if internals.metrics.thinking_steps}
											<div class="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-3 border border-orange-200 dark:border-orange-800">
												<div class="text-xs text-gray-600 dark:text-gray-400 mb-1">Thinking Steps</div>
												<div class="text-lg font-bold text-orange-700 dark:text-orange-300">
													{internals.metrics.thinking_steps}
												</div>
											</div>
										{/if}
									</div>
								</div>
							{/if}

							<!-- Available Tools -->
							{#if internals.tools && internals.tools.length > 0}
								<div>
									<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center">
										<span class="text-lg mr-2">🔧</span>
										{$i18n.t('Available Tools')} ({internals.tools.length})
									</h4>
									<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
										{#each internals.tools as tool, index}
											<div class="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-lg p-4 border border-green-200 dark:border-green-800 shadow-sm hover:shadow-md transition-shadow">
												<div class="flex items-start justify-between mb-2">
													<div class="flex items-center space-x-2">
														<span class="text-2xl">{getToolIcon(tool.name)}</span>
														<span class="font-mono text-sm font-bold text-green-700 dark:text-green-300">
															{tool.name}
														</span>
													</div>
													{#if tool.call_count}
														<span class="text-xs bg-green-200 dark:bg-green-800 text-green-800 dark:text-green-200 px-2 py-1 rounded-full">
															Called {tool.call_count}x
														</span>
													{/if}
												</div>
												<p class="text-xs text-gray-600 dark:text-gray-400 mb-2 leading-relaxed">
													{tool.description || 'No description available'}
												</p>
												{#if tool.parameters}
													<details class="mt-2">
														<summary class="text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
															Parameters →
														</summary>
														<div class="mt-2 bg-white dark:bg-gray-800 rounded p-2 border border-gray-200 dark:border-gray-700">
															<pre class="text-xs text-gray-700 dark:text-gray-300 overflow-x-auto">{formatJson(tool.parameters)}</pre>
														</div>
													</details>
												{/if}
												{#if getToolExecutionTime(tool)}
													<div class="mt-2 text-xs text-gray-500 dark:text-gray-400">
														⏱️ Execution: {getToolExecutionTime(tool)}
													</div>
												{/if}
											</div>
										{/each}
									</div>
								</div>
							{/if}

							<!-- System Instructions (Collapsible) -->
							{#if internals.system_prompt}
								<div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
									<button
										type="button"
										class="w-full text-left text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center justify-between cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
										on:click={() => systemInstructionsExpanded = !systemInstructionsExpanded}
									>
										<span class="flex items-center">
											📋 {$i18n.t('System Instructions')}
										</span>
										<svg
											class="w-4 h-4 transition-transform {systemInstructionsExpanded ? 'rotate-180' : ''}"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
										</svg>
									</button>
									
									
									{#if systemInstructionsExpanded}
										<div class="space-y-2">
											<!-- MD Preview Display Only -->
											<div class="relative bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 rounded-md p-3 border">
												<div class="flex gap-0 w-full" style="height: 400px;">
													<!-- Line numbers gutter for preview -->
													<div
														bind:this={previewLineNumbersElement}
														class="flex flex-col overflow-hidden select-none text-right pr-2 pl-1 py-2 text-xs text-gray-400 dark:text-gray-600 bg-gray-100 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700"
														style="min-width: 3rem; line-height: 1.5;"
													>
														{#each Array.from({ length: Math.max(internals.system_prompt ? internals.system_prompt.split('\n').length : 1, 4) }, (_, i) => i + 1) as lineNum}
															<div class="leading-normal">{lineNum}</div>
														{/each}
													</div>
													
													<!-- Preview content -->
													<div 
														bind:this={previewContentElement}
														class="text-xs w-full bg-transparent outline-hidden resize-none overflow-y-auto scrollbar-thin scrollbar-thumb-gray-400 dark:scrollbar-thumb-gray-600 scrollbar-track-gray-100 dark:scrollbar-track-gray-800 px-3 py-2 h-full"
														style="width: 100%; box-sizing: border-box;"
														on:scroll={syncPreviewScroll}
													>
														{#if internals.system_prompt.trim() === ''}
															<div class="text-gray-400 dark:text-gray-500 italic">
																{$i18n.t('No system prompt content to preview.')}
															</div>
														{:else}
															<div class="w-full prose prose-sm dark:prose-invert max-w-none text-gray-700 dark:text-gray-300">
																{@html DOMPurify.sanitize(marked.parse(internals.system_prompt))}
															</div>
														{/if}
													</div>
												</div>
											</div>
										</div>
									{/if}
								</div>
							{/if}

							<!-- Raw Internals (for debugging) -->
							<div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
								<button
									type="button"
									class="w-full text-left text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 flex items-center justify-between transition-colors"
									on:click={() => rawDataExpanded = !rawDataExpanded}
								>
									<span class="flex items-center">
										<svg class="w-3 h-3 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
										</svg>
										{$i18n.t('Raw Data (Developer View)')}
									</span>
									<svg
										class="w-4 h-4 transition-transform {rawDataExpanded ? 'rotate-180' : ''}"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
									</svg>
								</button>
								{#if rawDataExpanded}
									<pre class="mt-2 text-xs bg-gray-100 dark:bg-gray-900 p-3 rounded-md overflow-x-auto max-h-96 overflow-y-auto text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">{formatJson(internals)}</pre>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			</div>
		{/if}
	</div>
{/if}

<style>
	.strands-internals {
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
	}
	
	pre {
		font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
	}

	/* Smooth animations */
	@keyframes slideIn {
		from {
			opacity: 0;
			transform: translateY(-10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.strands-internals > div > div {
		animation: slideIn 0.3s ease-out;
	}

	/* Custom scrollbar */
	.strands-internals ::-webkit-scrollbar {
		width: 8px;
		height: 8px;
	}

	.strands-internals ::-webkit-scrollbar-track {
		background: rgba(0, 0, 0, 0.05);
		border-radius: 4px;
	}

	.strands-internals ::-webkit-scrollbar-thumb {
		background: rgba(0, 0, 0, 0.2);
		border-radius: 4px;
	}

	.strands-internals ::-webkit-scrollbar-thumb:hover {
		background: rgba(0, 0, 0, 0.3);
	}

	:global(.dark) .strands-internals ::-webkit-scrollbar-track {
		background: rgba(255, 255, 255, 0.05);
	}

	:global(.dark) .strands-internals ::-webkit-scrollbar-thumb {
		background: rgba(255, 255, 255, 0.2);
	}

	:global(.dark) .strands-internals ::-webkit-scrollbar-thumb:hover {
		background: rgba(255, 255, 255, 0.3);
	}
</style>
