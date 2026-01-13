<script lang="ts">
	import { onMount, tick } from 'svelte';

	export let value = '';
	export let placeholder = '';
	export let rows = 1;
	export let minSize = null;
	export let maxSize = null;
	export let required = false;
	export let readonly = false;
	export let className =
		'w-full rounded-lg px-3.5 py-2 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden h-full';

	export let onBlur = () => {};
	export let onScrollChange: (scrollTop: number) => void = () => {};
	export let initialScrollTop: number | null = null;
	
	let textareaElement: HTMLTextAreaElement;
	let lineNumbersElement: HTMLDivElement;
	let containerElement: HTMLDivElement;

	// Calculate line numbers based on value
	$: lineCount = value ? value.split('\n').length : 1;
	$: lineNumbers = Array.from({ length: Math.max(lineCount, rows) }, (_, i) => i + 1);

	// Expose method to set scroll position
	export const setScrollTop = (scrollTop: number) => {
		if (textareaElement) {
			textareaElement.scrollTop = scrollTop;
			if (lineNumbersElement) {
				lineNumbersElement.scrollTop = scrollTop;
			}
		}
	};

	// Expose method to get scroll position
	export const getScrollTop = (): number => {
		return textareaElement ? textareaElement.scrollTop : 0;
	};

	// Track if we've applied the initial scroll position
	let hasAppliedInitialScroll = false;
	let lastInitialScrollTop = null;

	// Watch for changes to initialScrollTop and apply them only when it's a new value
	$: if (textareaElement && initialScrollTop !== null && initialScrollTop !== lastInitialScrollTop) {
		setScrollTop(initialScrollTop);
		lastInitialScrollTop = initialScrollTop;
		hasAppliedInitialScroll = true;
	}

	// Adjust height on mount and after setting the element
	onMount(async () => {
		await tick();
		resize();

		// Apply initial scroll position if provided
		if (initialScrollTop !== null) {
			setScrollTop(initialScrollTop);
		}

		requestAnimationFrame(() => {
			// setInterval to check until textareaElement is set
			const interval = setInterval(() => {
				if (textareaElement) {
					clearInterval(interval);
					resize();
					// Apply scroll position again after resize
					if (initialScrollTop !== null) {
						setScrollTop(initialScrollTop);
					}
				}
			}, 100);
		});
	});

	const resize = () => {
		if (textareaElement) {
			textareaElement.style.height = '';

			let height = textareaElement.scrollHeight;
			if (maxSize && height > maxSize) {
				height = maxSize;
			}
			if (minSize && height < minSize) {
				height = minSize;
			}

			textareaElement.style.height = `${height}px`;
			
			// Sync line numbers container height
			if (lineNumbersElement) {
				lineNumbersElement.style.height = `${height}px`;
			}
		}
	};

	const syncScroll = () => {
		if (textareaElement && lineNumbersElement) {
			lineNumbersElement.scrollTop = textareaElement.scrollTop;
			onScrollChange(textareaElement.scrollTop);
		}
	};
</script>

<div class="flex gap-0 w-full" bind:this={containerElement}>
	<!-- Line numbers gutter -->
	<div
		bind:this={lineNumbersElement}
		class="flex flex-col overflow-hidden select-none text-right pr-2 pl-1 py-2 text-xs text-gray-400 dark:text-gray-600 bg-gray-100 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 rounded-l-lg"
		style="min-width: 3rem; line-height: 1.5;"
	>
		{#each lineNumbers as lineNum}
			<div class="leading-normal">{lineNum}</div>
		{/each}
	</div>

	<!-- Textarea -->
	<textarea
		bind:this={textareaElement}
		bind:value
		{placeholder}
		class="{className} rounded-l-none"
		style="field-sizing: content; font-family: monospace; line-height: 1.5;"
		{rows}
		{required}
		{readonly}
		on:input={(e) => {
			resize();
		}}
		on:focus={() => {
			resize();
		}}
		on:scroll={syncScroll}
		on:blur={onBlur}
	/>
</div>
