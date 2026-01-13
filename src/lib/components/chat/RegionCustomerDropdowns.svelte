<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { DropdownMenu } from 'bits-ui';
	import { flyAndScale } from '$lib/utils/transitions';
	
	const dispatch = createEventDispatcher();
	
	export let messageInput: any = null;
	
	let regions = ['eu', 'frankfurt', 'oregon', 'sydney', 'us'];
	let selectedRegion = '';
	let customers: string[] = [];
	let selectedCustomer = '';
	let loadingCustomers = false;
	let show = false; // Toggle state for dropdown menu
	
	// Fetch customers when region changes
	$: if (selectedRegion) {
		fetchCustomers(selectedRegion);
	}
	
	async function fetchCustomers(region: string) {
		if (!region) return;
		
		loadingCustomers = true;
		customers = [];
		selectedCustomer = '';
		
		try {
			const response = await fetch(`/api/v1/clickhouse/customers/${region}`, {
				method: 'GET',
				headers: {
					'Authorization': `Bearer ${localStorage.token}`,
					'Content-Type': 'application/json'
				}
			});
			
			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`);
			}
			
			const data = await response.json();
			customers = data.customers || [];
		} catch (error) {
			console.error('Error fetching customers:', error);
			toast.error('Failed to fetch customers for the selected region');
			customers = [];
		} finally {
			loadingCustomers = false;
		}
	}
	
	async function handleCustomerSelect() {
		if (selectedCustomer && messageInput) {
			try {
				// Insert the customer value with prefix at the current cursor position as plain text
				const textToInsert = `CustomerAdWebsite: ${selectedCustomer} `;
				await messageInput.insertPlainTextAtCursor(textToInsert);
				
				console.log('Customer inserted at cursor:', textToInsert);
				show = false; // Close the dropdown after selection
			} catch (error) {
				console.error('Error inserting customer:', error);
				// Fallback: dispatch event
				dispatch('insertCustomer', selectedCustomer);
			}
		}
	}
</script>

<DropdownMenu.Root bind:open={show}>
	<DropdownMenu.Trigger>
		<button
			class="flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
			aria-label="Customer Picker"
		>
			<div class=" m-auto self-center">
				<svg 
					class="size-5 text-gray-600 dark:text-gray-400"
					fill="none" 
					stroke="currentColor" 
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
				</svg>
			</div>
		</button>
	</DropdownMenu.Trigger>

	<DropdownMenu.Content
		class="w-full max-w-[240px] rounded-2xl px-3 py-3 border border-gray-100 dark:border-gray-800 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
		sideOffset={8}
		side="bottom"
		align="end"
		transition={flyAndScale}
	>
		<div class="flex flex-col gap-3">
			<div class="text-sm font-semibold text-gray-700 dark:text-gray-300">
				Customer Picker
			</div>

			<!-- Region Dropdown -->
			<div class="flex flex-col gap-1.5">
				<label for="region-select" class="text-xs font-medium text-gray-600 dark:text-gray-400">
					Region
				</label>
				<select
					id="region-select"
					bind:value={selectedRegion}
					class="px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-hidden"
				>
					<option value="">Select Region</option>
					{#each regions as region}
						<option value={region}>{region}</option>
					{/each}
				</select>
			</div>
			
			<!-- Customer Dropdown -->
			<div class="flex flex-col gap-1.5">
				<label for="customer-select" class="text-xs font-medium text-gray-600 dark:text-gray-400">
					Customer
				</label>
				<div class="relative">
					<select
						id="customer-select"
						bind:value={selectedCustomer}
						on:change={handleCustomerSelect}
						disabled={!selectedRegion || loadingCustomers}
						class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed outline-hidden"
					>
						<option value="">
							{#if loadingCustomers}
								Loading customers...
							{:else if !selectedRegion}
								Select region first
							{:else}
								Select Customer
							{/if}
						</option>
						{#each customers as customer}
							<option value={customer}>{customer}</option>
						{/each}
					</select>
					
					{#if loadingCustomers}
						<div class="absolute right-3 top-1/2 -translate-y-1/2 flex items-center pointer-events-none">
							<svg class="animate-spin h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
								<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
								<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
							</svg>
						</div>
					{/if}
				</div>
			</div>
		</div>
	</DropdownMenu.Content>
</DropdownMenu.Root>