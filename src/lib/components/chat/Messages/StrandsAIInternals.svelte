<script lang="ts">
	import { onMount } from 'svelte';
	import { fade, slide } from 'svelte/transition';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	export let internals: any = null;
	export let expanded: boolean = false;

	let showTools = false;
	let showChainOfThought = false;
	let showSystemPrompt = false;

	$: if (internals) {
		console.log('Strands AI Internals:', internals);
	}
</script>

{#if internals}
	<div class="strands-ai-internals mt-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800" transition:fade>
		<div class="flex items-center justify-between mb-2">
			<div class="flex items-center space-x-2">
				<div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
				<span class="text-xs font-medium text-blue-700 dark:text-blue-300">
					Strands AI Agent Internals
				</span>
			</div>
			<button
				class="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 transition"
				on:click={() => expanded = !expanded}
			>
				{expanded ? 'Collapse' : 'Expand'}
			</button>
		</div>

		{#if expanded}
			<div class="space-y-3" transition:slide>
				<!-- Model Information -->
				<div class="bg-white dark:bg-gray-800 rounded p-2">
					<div class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Model Info</div>
					<div class="text-xs text-gray-600 dark:text-gray-400">
						<div><strong>Model:</strong> {internals.model_info?.model_id || 'Unknown'}</div>
						<div><strong>Region:</strong> {internals.model_info?.aws_region || 'Unknown'}</div>
						<div><strong>Max Tokens:</strong> {internals.model_info?.max_tokens || 'Unknown'}</div>
					</div>
				</div>

				<!-- Tools Section -->
				<div class="bg-white dark:bg-gray-800 rounded p-2">
					<button
						class="flex items-center justify-between w-full text-xs font-medium text-gray-700 dark:text-gray-300 mb-1"
						on:click={() => showTools = !showTools}
					>
						<span>Available Tools ({internals.tools?.length || 0})</span>
						<span class="transform transition-transform {showTools ? 'rotate-180' : ''}">▼</span>
					</button>
					
					{#if showTools && internals.tools}
						<div class="space-y-1 mt-2" transition:slide>
							{#each internals.tools as tool}
								<div class="p-2 bg-gray-50 dark:bg-gray-700 rounded text-xs">
									<div class="font-medium text-gray-800 dark:text-gray-200">{tool.name}</div>
									{#if tool.description}
										<div class="text-gray-600 dark:text-gray-400 mt-1 text-xs">
											{tool.description.split('\n')[0]}
										</div>
									{/if}
								</div>
							{/each}
						</div>
					{/if}
				</div>

				<!-- Chain of Thought Section -->
				{#if internals.chain_of_thought && internals.chain_of_thought.length > 0}
					<div class="bg-white dark:bg-gray-800 rounded p-2">
						<button
							class="flex items-center justify-between w-full text-xs font-medium text-gray-700 dark:text-gray-300 mb-1"
							on:click={() => showChainOfThought = !showChainOfThought}
						>
							<span>Chain of Thought ({internals.chain_of_thought.length})</span>
							<span class="transform transition-transform {showChainOfThought ? 'rotate-180' : ''}">▼</span>
						</button>
						
						{#if showChainOfThought}
							<div class="space-y-2 mt-2" transition:slide>
								{#each internals.chain_of_thought as thought, index}
									<div class="p-2 bg-gray-50 dark:bg-gray-700 rounded">
										<div class="flex items-center justify-between mb-1">
											<span class="text-xs font-medium text-gray-800 dark:text-gray-200">
												Step {index + 1}
											</span>
											{#if thought.timestamp}
												<span class="text-xs text-gray-500 dark:text-gray-400">
													{new Date(thought.timestamp).toLocaleTimeString()}
												</span>
											{/if}
										</div>
										<div class="text-xs text-gray-600 dark:text-gray-400">
											{#if thought.type === 'tool_call'}
												<div class="flex items-center space-x-1">
													<span class="w-2 h-2 bg-green-500 rounded-full"></span>
													<span><strong>Tool:</strong> {thought.tool_name}</span>
												</div>
												{#if thought.args}
													<div class="mt-1 pl-3">
														<strong>Args:</strong> {JSON.stringify(thought.args)}
													</div>
												{/if}
											{:else if thought.type === 'reasoning'}
												<div class="flex items-center space-x-1">
													<span class="w-2 h-2 bg-blue-500 rounded-full"></span>
													<span><strong>Reasoning:</strong></span>
												</div>
												<div class="mt-1 pl-3">{thought.content}</div>
											{:else}
												<pre class="whitespace-pre-wrap text-xs">{JSON.stringify(thought, null, 2)}</pre>
											{/if}
										</div>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				{/if}

				<!-- System Prompt Section -->
				<div class="bg-white dark:bg-gray-800 rounded p-2">
					<button
						class="flex items-center justify-between w-full text-xs font-medium text-gray-700 dark:text-gray-300 mb-1"
						on:click={() => showSystemPrompt = !showSystemPrompt}
					>
						<span>System Prompt</span>
						<span class="transform transition-transform {showSystemPrompt ? 'rotate-180' : ''}">▼</span>
					</button>
					
					{#if showSystemPrompt && internals.system_prompt}
						<div class="mt-2" transition:slide>
							<div class="p-2 bg-gray-50 dark:bg-gray-700 rounded text-xs text-gray-600 dark:text-gray-400 max-h-32 overflow-y-auto">
								<pre class="whitespace-pre-wrap">{internals.system_prompt}</pre>
							</div>
						</div>
					{/if}
				</div>
			</div>
		{:else}
			<!-- Collapsed view - show summary -->
			<div class="text-xs text-blue-600 dark:text-blue-400">
				<span>{internals.tools?.length || 0} tools available</span>
				{#if internals.chain_of_thought && internals.chain_of_thought.length > 0}
					<span class="ml-2">• {internals.chain_of_thought.length} reasoning steps</span>
				{/if}
			</div>
		{/if}
	</div>
{/if}

<style>
	.strands-ai-internals {
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
	}
	
	pre {
		font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
		font-size: 10px;
		line-height: 1.4;
	}
	
	.animate-pulse {
		animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
	}
	
	@keyframes pulse {
		0%, 100% {
			opacity: 1;
		}
		50% {
			opacity: 0.5;
		}
	}
</style>
