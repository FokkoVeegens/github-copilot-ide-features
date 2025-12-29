const { createApp, ref, computed, onMounted } = Vue;

createApp({
    setup() {
        // Reactive state
        const loading = ref(true);
        const error = ref(null);
        const metadata = ref({ ides: [], flags: {} });
        const features = ref([]);
        const showLegend = ref(false);
        const searchTerm = ref('');
        const selectedTags = ref([]);
        const showDeprecated = ref(false);
        const tooltip = ref({
            visible: false,
            text: '',
            x: 0,
            y: 0
        });

        // Computed properties
        const allTags = computed(() => {
            const tagSet = new Set();
            features.value.forEach(f => {
                if (Array.isArray(f.tags)) {
                    f.tags.forEach(tag => tagSet.add(tag));
                }
            });
            return Array.from(tagSet).sort();
        });

        const filteredFeatures = computed(() => {
            let filtered = features.value.slice();

            // Filter by selected tags
            if (selectedTags.value.length > 0) {
                filtered = filtered.filter(f => 
                    selectedTags.value.every(tag => f.tags && f.tags.includes(tag))
                );
            }

            // Filter by search term
            if (searchTerm.value.trim()) {
                const lowerSearchTerm = searchTerm.value.toLowerCase();
                filtered = filtered.filter(feature => {
                    const nameMatch = feature.name.toLowerCase().includes(lowerSearchTerm);
                    const descMatch = feature.description && 
                                     feature.description.toLowerCase().includes(lowerSearchTerm);
                    return nameMatch || descMatch;
                });
            }

            // Filter out deprecated features unless explicitly shown
            if (!showDeprecated.value) {
                filtered = filtered.filter(feature => {
                    return Object.values(feature.availability || {}).some(
                        avail => avail.stage !== 'DEP'
                    );
                });
            }

            // Sort features by name alphabetically
            return filtered.sort((a, b) => a.name.localeCompare(b.name));
        });

        // Methods
        const toggleTag = (tag) => {
            const index = selectedTags.value.indexOf(tag);
            if (index > -1) {
                selectedTags.value.splice(index, 1);
            } else {
                selectedTags.value.push(tag);
            }
        };

        const performSearch = () => {
            // Search is reactive, so this is just a placeholder
            // The computed property handles the actual filtering
        };

        const clearSearch = () => {
            searchTerm.value = '';
        };

        const showTooltip = (event, text) => {
            if (!text) return;
            tooltip.value.text = text;
            tooltip.value.visible = true;
            positionTooltip(event);
        };

        const moveTooltip = (event) => {
            if (tooltip.value.visible) {
                positionTooltip(event);
            }
        };

        const hideTooltip = () => {
            tooltip.value.visible = false;
        };

        const positionTooltip = (event) => {
            const offset = 16;
            let x = event.clientX + offset;
            let y = event.clientY + offset;

            // Note: We can't get the tooltip dimensions here easily
            // Vue will handle this in the next tick, but for simplicity
            // we'll use basic positioning
            tooltip.value.x = x;
            tooltip.value.y = y;
        };

        const loadData = async () => {
            try {
                const [featuresResponse, metadataResponse] = await Promise.all([
                    fetch('data/features.json'),
                    fetch('data/metadata.json')
                ]);

                if (!featuresResponse.ok || !metadataResponse.ok) {
                    throw new Error('Failed to load data files');
                }

                const featuresData = await featuresResponse.json();
                metadata.value = await metadataResponse.json();
                features.value = featuresData.features;
                loading.value = false;
            } catch (err) {
                console.error('Error loading data:', err);
                error.value = err.message;
                loading.value = false;
            }
        };

        // Lifecycle
        onMounted(() => {
            loadData();
        });

        return {
            loading,
            error,
            metadata,
            features,
            showLegend,
            searchTerm,
            selectedTags,
            showDeprecated,
            tooltip,
            allTags,
            filteredFeatures,
            toggleTag,
            performSearch,
            clearSearch,
            showTooltip,
            moveTooltip,
            hideTooltip
        };
    }
}).mount('#app');
