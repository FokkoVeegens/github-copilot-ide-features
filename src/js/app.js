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
        const tooltipEl = ref(null);
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

        // Compute tag counts based on current filters
        const tagCounts = computed(() => {
            const counts = {};
            
            // First, filter by search term and deprecated setting (not by tags)
            let baseFiltered = features.value.slice();
            
            // Filter by search term
            if (searchTerm.value.trim()) {
                const lowerSearchTerm = searchTerm.value.toLowerCase();
                baseFiltered = baseFiltered.filter(feature => {
                    const nameMatch = feature.name.toLowerCase().includes(lowerSearchTerm);
                    const descMatch = feature.description && 
                                     feature.description.toLowerCase().includes(lowerSearchTerm);
                    return nameMatch || descMatch;
                });
            }
            
            // Filter out deprecated features unless explicitly shown
            if (!showDeprecated.value) {
                baseFiltered = baseFiltered.filter(feature => {
                    return Object.values(feature.availability || {}).some(
                        avail => avail.stage !== 'DEP'
                    );
                });
            }
            
            // For each tag, count how many features would match if that tag was added to the filter
            allTags.value.forEach(tag => {
                let filtered = baseFiltered.slice();
                
                // Apply current selected tags plus this tag
                const tagsToCheck = [...selectedTags.value];
                if (!tagsToCheck.includes(tag)) {
                    tagsToCheck.push(tag);
                }
                
                filtered = filtered.filter(f => 
                    tagsToCheck.every(t => f.tags && f.tags.includes(t))
                );
                
                counts[tag] = filtered.length;
            });
            
            return counts;
        });

        // Visible tags: only show tags with results > 0
        const visibleTags = computed(() => {
            // If no filters are active, show all tags
            if (selectedTags.value.length === 0 && !searchTerm.value.trim()) {
                return allTags.value;
            }
            
            // Otherwise, only show tags that have results
            return allTags.value.filter(tag => tagCounts.value[tag] > 0);
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

        const getStageTooltip = (stage) => {
            return metadata.value.stages[stage]?.name || '';
        };

        const positionTooltip = (event) => {
            if (!tooltipEl.value) return;

            const offset = 16;
            let x = event.clientX + offset;
            let y = event.clientY + offset;

            const tooltipRect = tooltipEl.value.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;

            // Prevent tooltip from going off the right edge
            if (x + tooltipRect.width > viewportWidth - 8) {
                x = event.clientX - tooltipRect.width - offset;
            }

            // Prevent tooltip from going off the bottom edge
            if (y + tooltipRect.height > viewportHeight - 8) {
                y = event.clientY - tooltipRect.height - offset;
            }

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
            tooltipEl,
            tooltip,
            allTags,
            visibleTags,
            tagCounts,
            filteredFeatures,
            toggleTag,
            performSearch,
            clearSearch,
            showTooltip,
            moveTooltip,
            hideTooltip,
            getStageTooltip
        };
    }
}).mount('#app');
