        const FEATURES_URL = 'data/features.json';
        const METADATA_URL = 'data/metadata.json';

        let metadata = {};
        let features = [];

        async function loadData() {
            try {
                const [featuresResponse, metadataResponse] = await Promise.all([
                    fetch(FEATURES_URL),
                    fetch(METADATA_URL)
                ]);

                if (!featuresResponse.ok || !metadataResponse.ok) {
                    throw new Error('Failed to load data files');
                }

                const featuresData = await featuresResponse.json();
                metadata = await metadataResponse.json();
                features = featuresData.features;

                renderFeatureTable();
            } catch (error) {
                console.error('Error loading data:', error);
                document.getElementById('content').innerHTML = `
                    <div class="error">
                        <strong>Error loading data:</strong> ${error.message}
                    </div>
                `;
            }
        }

        // Removed obsolete function definition
        function renderFeatureTable() {
            const contentDiv = document.getElementById('content');
            contentDiv.innerHTML = '';

            // Collect all unique tags
            const tagSet = new Set();
            features.forEach(f => {
                if (Array.isArray(f.tags)) {
                    f.tags.forEach(tag => tagSet.add(tag));
                }
            });
            const allTags = Array.from(tagSet).sort();

            // Selected tags state
            let selectedTags = [];

            // Tag badges UI
            const tagsDiv = document.createElement('div');
            tagsDiv.className = 'tags-bar';
            allTags.forEach(tag => {
                const badge = document.createElement('span');
                badge.className = 'tag-badge';
                badge.textContent = tag;
                badge.onclick = () => {
                    if (selectedTags.includes(tag)) {
                        selectedTags = selectedTags.filter(t => t !== tag);
                        badge.classList.remove('selected');
                    } else {
                        selectedTags.push(tag);
                        badge.classList.add('selected');
                    }
                    updateTable();
                };
                tagsDiv.appendChild(badge);
            });
            contentDiv.appendChild(tagsDiv);

            // Table wrapper
            const tableWrapper = document.createElement('div');
            tableWrapper.className = 'table-wrapper';
            contentDiv.appendChild(tableWrapper);

            function updateTable() {
                tableWrapper.innerHTML = '';
                const table = document.createElement('table');
                const thead = document.createElement('thead');
                const headerRow = document.createElement('tr');
                headerRow.innerHTML = '<th>Feature</th>';
                metadata.ides.forEach(ide => {
                    const th = document.createElement('th');
                    th.textContent = ide.name;
                    headerRow.appendChild(th);
                });
                thead.appendChild(headerRow);
                table.appendChild(thead);

                const tbody = document.createElement('tbody');
                let filtered = features;
                if (selectedTags.length > 0) {
                    filtered = features.filter(f => selectedTags.every(tag => f.tags && f.tags.includes(tag)));
                }
                filtered.forEach(feature => {
                    const row = document.createElement('tr');
                    const nameCell = document.createElement('td');
                    // Feature name
                    const nameText = document.createElement('div');
                    nameText.textContent = feature.name;
                    nameCell.appendChild(nameText);
                    // Feature tags as mini badges
                    if (Array.isArray(feature.tags) && feature.tags.length > 0) {
                        const tagsWrap = document.createElement('div');
                        tagsWrap.style.marginTop = '4px';
                        feature.tags.forEach(tag => {
                            const badge = document.createElement('span');
                            badge.className = 'feature-mini-badge';
                            badge.textContent = tag;
                            tagsWrap.appendChild(badge);
                        });
                        nameCell.appendChild(tagsWrap);
                    }
                    row.appendChild(nameCell);
                    metadata.ides.forEach(ide => {
                        const cell = document.createElement('td');
                        cell.className = 'availability-cell';
                        const availability = feature.availability[ide.id];
                        if (availability) {
                            const link = document.createElement('a');
                            link.href = availability.url || '#';
                            link.className = `status-badge ${availability.stage}`;
                            link.target = '_blank';
                            link.rel = 'noopener noreferrer';
                            let badgeContent = availability.stage;
                            if (availability.flags && availability.flags.length > 0) {
                                const flagIcons = availability.flags.map(flagId => {
                                    const flag = metadata.flags[flagId];
                                    return flag ? flag.icon : '';
                                }).filter(icon => icon).join(' ');
                                if (flagIcons) {
                                    badgeContent += ` <span class="flag-icon">${flagIcons}</span>`;
                                }
                            }
                            link.innerHTML = badgeContent;
                            if (availability.stage !== 'DEP') {
                                const checkmark = document.createElement('span');
                                checkmark.className = 'checkmark';
                                checkmark.textContent = '✅';
                                cell.appendChild(checkmark);
                            }
                            cell.appendChild(link);
                        } else {
                            cell.innerHTML = '<span class="not-available">❌</span>';
                        }
                        row.appendChild(cell);
                    });
                    tbody.appendChild(row);
                });
                table.appendChild(tbody);
                tableWrapper.appendChild(table);
                // Update tag badge selection UI
                Array.from(tagsDiv.children).forEach(badge => {
                    if (selectedTags.includes(badge.textContent)) {
                        badge.classList.add('selected');
                    } else {
                        badge.classList.remove('selected');
                    }
                });
            }

            updateTable();
        }

        loadData();
