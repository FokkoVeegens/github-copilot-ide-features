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

                renderTables();
            } catch (error) {
                console.error('Error loading data:', error);
                document.getElementById('content').innerHTML = `
                    <div class="error">
                        <strong>Error loading data:</strong> ${error.message}
                    </div>
                `;
            }
        }

        function renderTables() {
            const categories = {};
            
            features.forEach(feature => {
                const category = feature.category || 'other';
                if (!categories[category]) {
                    categories[category] = [];
                }
                categories[category].push(feature);
            });

            const contentDiv = document.getElementById('content');
            contentDiv.innerHTML = '';

            Object.keys(categories).sort().forEach(category => {
                const section = document.createElement('div');
                section.className = 'category-section';

                const header = document.createElement('div');
                header.className = 'category-header';
                header.innerHTML = `
                    <h2>${category}</h2>
                    <span class="category-count">${categories[category].length} feature${categories[category].length !== 1 ? 's' : ''}</span>
                `;
                section.appendChild(header);

                const tableWrapper = document.createElement('div');
                tableWrapper.className = 'table-wrapper';

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
                
                categories[category].forEach(feature => {
                    const row = document.createElement('tr');
                    
                    const nameCell = document.createElement('td');
                    nameCell.textContent = feature.name;
                    row.appendChild(nameCell);

                    metadata.ides.forEach(ide => {
                        const cell = document.createElement('td');
                        cell.className = 'availability-cell';
                        
                        const availability = feature.availability[ide.id];
                        
                        if (availability) {
                            const checkmark = document.createElement('span');
                            checkmark.className = 'checkmark';
                            checkmark.textContent = '✅';
                            
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
                            cell.appendChild(checkmark);
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
                section.appendChild(tableWrapper);
                contentDiv.appendChild(section);
            });
        }

        loadData();
