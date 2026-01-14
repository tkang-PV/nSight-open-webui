<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Switch from '$lib/components/common/Switch.svelte';
	import { getLogConfig, updateLogConfig, getLogInfo, getLogFiles, getLogContent } from '$lib/apis/logs';

	const i18n = getContext('i18n');

	export let saveHandler: Function;

	let loading = false;
	let logConfig = {
		enable: false,
		path: '',
		max_size: '10MB',
		backup_count: 5,
		format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
		date_format: '%Y-%m-%d %H:%M:%S'
	};

	let logInfo = null;
	let logFiles = [];
	let logContent = '';
	let selectedFileIndex = 0;
	let linesToShow = 100;
	let showLogViewer = false;

	const loadLogConfig = async () => {
		try {
			const config = await getLogConfig(localStorage.token);
			if (config) {
				logConfig = { ...logConfig, ...config };
			}
		} catch (error) {
			console.error('Failed to load log config:', error);
			toast.error($i18n.t('Failed to load log configuration'));
		}
	};

	const loadLogInfo = async () => {
		try {
			const info = await getLogInfo(localStorage.token);
			if (info) {
				logInfo = info;
			}
		} catch (error) {
			console.error('Failed to load log info:', error);
		}
	};

	const loadLogFiles = async () => {
		try {
			const files = await getLogFiles(localStorage.token);
			if (files) {
				logFiles = files;
			}
		} catch (error) {
			console.error('Failed to load log files:', error);
		}
	};

	const loadLogContent = async () => {
		try {
			const content = await getLogContent(localStorage.token, linesToShow, selectedFileIndex);
			if (content) {
				logContent = content.content || '';
			}
		} catch (error) {
			console.error('Failed to load log content:', error);
			toast.error($i18n.t('Failed to load log content'));
		}
	};

	const refreshLogData = async () => {
		if (logConfig.enable) {
			await Promise.all([loadLogInfo(), loadLogFiles()]);
		}
	};

	const updateHandler = async () => {
		loading = true;
		try {
			const res = await updateLogConfig(localStorage.token, logConfig);
			if (res) {
				toast.success($i18n.t('Log settings saved successfully!'));
				await refreshLogData();
				saveHandler();
			}
		} catch (error) {
			console.error('Failed to update log config:', error);
			toast.error($i18n.t('Failed to update log settings'));
		} finally {
			loading = false;
		}
	};

	const formatFileSize = (bytes) => {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
	};

	const formatDate = (timestamp) => {
		return new Date(timestamp * 1000).toLocaleString();
	};

	onMount(async () => {
		await loadLogConfig();
		await refreshLogData();
	});

	$: if (logConfig.enable) {
		refreshLogData();
	}
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	on:submit|preventDefault={updateHandler}
>
	<div class="mt-0.5 space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		<div class="">
			<div class="mb-3.5">
				<div class="mb-2.5 text-base font-medium">{$i18n.t('Log Settings')}</div>

				<hr class="border-gray-100 dark:border-gray-850 my-2" />

				<div class="mb-2.5 flex w-full justify-between pr-2">
					<div class="self-center text-xs font-medium">{$i18n.t('Enable Log to File')}</div>
					<Switch bind:state={logConfig.enable} />
				</div>

				{#if logConfig.enable}
					<div class="space-y-3">
						<div class="mb-2.5">
							<div class="self-center text-xs font-medium mb-2">
								{$i18n.t('Log Path')}
							</div>
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
								type="text"
								placeholder={$i18n.t('Enter log directory path')}
								bind:value={logConfig.path}
							/>
							<div class="mt-1 text-xs text-gray-400 dark:text-gray-500">
								{$i18n.t('Directory where log files will be stored. Files will be named open-webui_{timestamp}.log')}
							</div>
						</div>

						<div class="flex gap-4">
							<div class="flex-1">
								<div class="self-center text-xs font-medium mb-2">
									{$i18n.t('Max File Size')}
								</div>
								<input
									class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
									type="text"
									placeholder="10MB"
									bind:value={logConfig.max_size}
								/>
								<div class="mt-1 text-xs text-gray-400 dark:text-gray-500">
									{$i18n.t('e.g., 10MB, 1GB')}
								</div>
							</div>

							<div class="flex-1">
								<div class="self-center text-xs font-medium mb-2">
									{$i18n.t('Backup Count')}
								</div>
								<input
									class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
									type="number"
									min="1"
									max="50"
									bind:value={logConfig.backup_count}
								/>
								<div class="mt-1 text-xs text-gray-400 dark:text-gray-500">
									{$i18n.t('Number of backup files to keep')}
								</div>
							</div>
						</div>

						<div class="mb-2.5">
							<div class="self-center text-xs font-medium mb-2">
								{$i18n.t('Log Format')}
							</div>
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
								type="text"
								bind:value={logConfig.format}
							/>
							<div class="mt-1 text-xs text-gray-400 dark:text-gray-500">
								{$i18n.t('Python logging format string')}
							</div>
						</div>

						<div class="mb-2.5">
							<div class="self-center text-xs font-medium mb-2">
								{$i18n.t('Date Format')}
							</div>
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
								type="text"
								bind:value={logConfig.date_format}
							/>
							<div class="mt-1 text-xs text-gray-400 dark:text-gray-500">
								{$i18n.t('Python strftime format for timestamps')}
							</div>
						</div>
					</div>
				{/if}
			</div>

			{#if logConfig.enable && logInfo}
				<div class="mb-3">
					<div class="mb-2.5 text-base font-medium">{$i18n.t('Log File Status')}</div>

					<hr class="border-gray-100 dark:border-gray-850 my-2" />

					<div class="space-y-2">
						<div class="flex justify-between items-center">
							<span class="text-xs font-medium">{$i18n.t('Status')}:</span>
							<span class="text-xs {logInfo.enabled ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}">
								{logInfo.enabled ? $i18n.t('Enabled') : $i18n.t('Disabled')}
							</span>
						</div>

						{#if logInfo.exists}
							<div class="flex justify-between items-center">
								<span class="text-xs font-medium">{$i18n.t('File Size')}:</span>
								<span class="text-xs">{formatFileSize(logInfo.size)}</span>
							</div>

							<div class="flex justify-between items-center">
								<span class="text-xs font-medium">{$i18n.t('Last Modified')}:</span>
								<span class="text-xs">{formatDate(logInfo.modified)}</span>
							</div>
						{/if}

						<div class="flex justify-between items-center">
							<span class="text-xs font-medium">{$i18n.t('Max Size')}:</span>
							<span class="text-xs">{logInfo.max_size}</span>
						</div>

						<div class="flex justify-between items-center">
							<span class="text-xs font-medium">{$i18n.t('Backup Count')}:</span>
							<span class="text-xs">{logInfo.backup_count}</span>
						</div>
					</div>
				</div>

				<div class="mb-3">
					<div class="mb-2.5 text-base font-medium flex justify-between items-center">
						<span>{$i18n.t('Log Viewer')}</span>
						<button
							type="button"
							class="text-xs px-3 py-1.5 bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition rounded-lg font-medium"
							on:click={() => {
								showLogViewer = !showLogViewer;
								if (showLogViewer && !logContent) {
									loadLogContent();
								}
							}}
						>
							{showLogViewer ? $i18n.t('Hide') : $i18n.t('Show')} {$i18n.t('Logs')}
						</button>
					</div>

					{#if showLogViewer}
						<hr class="border-gray-100 dark:border-gray-850 my-2" />

						<div class="space-y-3">
							<div class="flex gap-4">
								<div class="flex-1">
									<div class="self-center text-xs font-medium mb-2">
										{$i18n.t('Log File')}
									</div>
									<select
										class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
										bind:value={selectedFileIndex}
										on:change={loadLogContent}
									>
										{#each logFiles as file, index}
											<option value={index}>
												{file.name} ({formatFileSize(file.size)})
												{file.is_main ? '(Current)' : '(Backup)'}
											</option>
										{/each}
									</select>
								</div>

								<div class="flex-1">
									<div class="self-center text-xs font-medium mb-2">
										{$i18n.t('Lines to Show')}
									</div>
									<select
										class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
										bind:value={linesToShow}
										on:change={loadLogContent}
									>
										<option value={50}>50</option>
										<option value={100}>100</option>
										<option value={200}>200</option>
										<option value={500}>500</option>
										<option value={1000}>1000</option>
									</select>
								</div>

								<div class="flex items-end">
									<button
										type="button"
										class="px-3 py-2 text-xs bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition rounded-lg font-medium"
										on:click={loadLogContent}
									>
										{$i18n.t('Refresh')}
									</button>
								</div>
							</div>

							<div class="mb-2.5">
								<div class="self-center text-xs font-medium mb-2">
									{$i18n.t('Log Content')}
								</div>
								<div class="w-full h-64 rounded-lg bg-gray-50 dark:bg-gray-850 p-3 overflow-auto">
									<pre class="text-xs font-mono whitespace-pre-wrap text-gray-700 dark:text-gray-300">{logContent || $i18n.t('No log content available')}</pre>
								</div>
							</div>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
			disabled={loading}
		>
			{loading ? $i18n.t('Saving...') : $i18n.t('Save')}
		</button>
	</div>
</form>
