import { WEBUI_API_BASE_URL } from '$lib/constants';

export const getModelItems = async (
	token: string = '',
	query,
	viewOption,
	selectedTag,
	orderBy,
	direction,
	page
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (query) {
		searchParams.append('query', query);
	}
	if (viewOption) {
		searchParams.append('view_option', viewOption);
	}
	if (selectedTag) {
		searchParams.append('tag', selectedTag);
	}
	if (orderBy) {
		searchParams.append('order_by', orderBy);
	}
	if (direction) {
		searchParams.append('direction', direction);
	}
	if (page) {
		searchParams.append('page', page.toString());
	}

	const res = await fetch(`${WEBUI_API_BASE_URL}/models/list?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getModelTags = async (token: string = '') => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/models/tags`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const importModels = async (token: string, models: object[]) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/models/import`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify({ models: models })
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getBaseModels = async (token: string = '') => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/models/base`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const createNewModel = async (token: string, model: object) => {
	let error = null;

	console.log('[API createNewModel] ===== createNewModel START =====');
	console.log('[API createNewModel] model type:', typeof model);
	console.log('[API createNewModel] model keys:', Object.keys(model));
	console.log('[API createNewModel] model.meta type:', typeof model.meta);
	if (model.meta) {
		console.log('[API createNewModel] model.meta keys:', Object.keys(model.meta));
		if (model.meta.strands) {
			console.log('[API createNewModel] ✓ Found model.meta.strands:', model.meta.strands);
		} else {
			console.warn('[API createNewModel] ⚠️ model.meta.strands NOT found');
			console.log('[API createNewModel] Available meta keys:', Object.keys(model.meta));
		}
	} else {
		console.warn('[API createNewModel] model.meta is not present');
	}
	
	console.log('[API createNewModel] Full request body:', JSON.stringify(model, null, 2));

	const res = await fetch(`${WEBUI_API_BASE_URL}/models/create`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(model)
	})
		.then(async (res) => {
			console.log('[API createNewModel] Response status:', res.status);
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			console.log('[API createNewModel] Response JSON received');
			console.log('[API createNewModel] ===== createNewModel END =====');
			return json;
		})
		.catch((err) => {
			error = err.detail;
			console.error('[API createNewModel] Error:', err);
			console.error('[API createNewModel] ===== createNewModel END (ERROR) =====');
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getModelById = async (token: string, id: string) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('id', id);

	const res = await fetch(`${WEBUI_API_BASE_URL}/models/model?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err;

			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const toggleModelById = async (token: string, id: string) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('id', id);

	const res = await fetch(`${WEBUI_API_BASE_URL}/models/model/toggle?${searchParams.toString()}`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err;

			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateModelById = async (token: string, id: string, model: object) => {
	let error = null;

	console.log('[API updateModelById] ===== updateModelById START =====');
	console.log('[API updateModelById] Model ID:', id);
	console.log('[API updateModelById] model type:', typeof model);
	console.log('[API updateModelById] model keys:', Object.keys(model));
	console.log('[API updateModelById] model.meta type:', typeof model.meta);
	if (model.meta) {
		console.log('[API updateModelById] model.meta keys:', Object.keys(model.meta));
		if (model.meta.strands) {
			console.log('[API updateModelById] ✓ Found model.meta.strands:', model.meta.strands);
		} else {
			console.warn('[API updateModelById] ⚠️ model.meta.strands NOT found');
			console.log('[API updateModelById] Available meta keys:', Object.keys(model.meta));
		}
	} else {
		console.warn('[API updateModelById] model.meta is not present');
	}
	
	const requestBody = { ...model, id };
	console.log('[API updateModelById] Request body keys:', Object.keys(requestBody));
	console.log('[API updateModelById] Request body.meta.strands:', requestBody.meta?.strands);
	console.log('[API updateModelById] Full request body:', JSON.stringify(requestBody, null, 2));

	const res = await fetch(`${WEBUI_API_BASE_URL}/models/model/update`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(requestBody)
	})
		.then(async (res) => {
			console.log('[API updateModelById] Response status:', res.status);
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			console.log('[API updateModelById] Response JSON received');
			console.log('[API updateModelById] ===== updateModelById END =====');
			return json;
		})
		.catch((err) => {
			error = err;

			console.error('[API updateModelById] Error:', err);
			console.error('[API updateModelById] ===== updateModelById END (ERROR) =====');
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const deleteModelById = async (token: string, id: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/models/model/delete`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify({ id })
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err.detail;

			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const deleteAllModels = async (token: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/models/delete/all`, {
		method: 'DELETE',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err;

			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
