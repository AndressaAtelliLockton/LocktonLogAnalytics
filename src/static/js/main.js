document.addEventListener('DOMContentLoaded', () => {
    // Inicializa ícones Lucide
    lucide.createIcons();

    // --- Controle de Popups/Tooltips (Ação de Clique) ---
    document.addEventListener('click', (e) => {
        const infoContainer = e.target.closest('.group');
        
        // Fecha todos os popups abertos caso o usuário clique fora deles
        document.querySelectorAll('.group .absolute').forEach(tooltip => {
            if (tooltip.classList.contains('group-hover:block')) {
                if (!infoContainer || tooltip.parentNode !== infoContainer) {
                    tooltip.classList.add('hidden');
                    tooltip.classList.remove('block');
                }
            }
        });

        // Se o usuário clicou no ícone de info, alterna a exibição do popup
        if (infoContainer && infoContainer.querySelector('[data-lucide="info"]')) {
            const tooltip = infoContainer.querySelector('.absolute');
            if (tooltip && tooltip.classList.contains('group-hover:block')) {
                tooltip.classList.toggle('hidden');
                tooltip.classList.toggle('block');
            }
        }
    });

    const uploadForm = document.getElementById('upload-form');
    const loadGraylogBtn = document.getElementById('load-graylog-btn');
    const loadingStatus = document.getElementById('loading-status');
    const resetFiltersBtn = document.getElementById('reset-filters-btn');
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const menuToggleBtn = document.getElementById('menu-toggle-btn');
    const sidebar = document.getElementById('sidebar');
    let volumeChart = null;
    let forecastChart = null;
    let rumVitalsChart = null;
    let rumErrorsChart = null;
    let infraCpuChart = null;
    let infraMemChart = null;
    let infraDiskChart = null;
    let apiStatusChart = null;
    let apiMethodChart = null;
    let apiEndpointChart = null;
    let cicdStatusChart = null;
    let cicdDurationChart = null;
    let metricChart = null;
    
    // Elementos do Modal
    const logModal = document.getElementById('log-details-modal');
    const modalContent = document.getElementById('modal-log-content');
    const closeModalSpan = document.querySelector('.close-modal');
    const chatHistoryDiv = document.getElementById('modal-chat-history');
    const chatInput = document.getElementById('modal-chat-input');
    const chatSendBtn = document.getElementById('modal-chat-send');
    let currentChatMessages = []; // Armazena histórico do chat atual
    let isPatternView = false; // Estado da visualização (Lista vs Padrões)

    // --- Controle do Loader Global ---
    let activeRequests = 0;
    function startGlobalLoading() {
        activeRequests++;
        const loader = document.getElementById('global-loader');
        if (loader) loader.classList.remove('hidden');
    }
    function stopGlobalLoading() {
        activeRequests--;
        if (activeRequests <= 0) {
            activeRequests = 0;
            const loader = document.getElementById('global-loader');
            if (loader) loader.classList.add('hidden');
        }
    }
    // ---------------------------------

    // Elementos do Modal Jira
    const jiraModal = document.getElementById('jira-ticket-modal');
    const closeJiraModal = document.getElementById('close-jira-modal');
    const btnSubmitJira = document.getElementById('btn-submit-jira');
    const jiraStatus = document.getElementById('jira-submit-status');

    // Estado da Investigação
    let currentPage = 1;
    let currentFilters = {
        search: "",
        level: "Todos",
        source: "Todos"
    };

    // Handler for CSV upload
    if (uploadForm) {
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('csv-file');
        if (fileInput.files.length === 0) {
            loadingStatus.textContent = 'Por favor, selecione um arquivo.';
            loadingStatus.style.color = 'red';
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        showLoading('Enviando e processando CSV...');
        startGlobalLoading();
        try {
            const response = await fetch('/api/upload-csv', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Erro no servidor');
            }

            const result = await response.json();
            showSuccess(`Sucesso! ${result.records} logs processados.`);
            await fetchAndRenderSummary();
            await loadFilters(); // Carrega filtros para a aba de investigação
        } catch (error) {
            showError(`Erro no upload: ${error.message}`);
        } finally {
            stopGlobalLoading();
        }
    });
    }

    // --- Lógica de Auto-Update do Graylog ---
    let autoUpdateInterval = null;
    const AUTO_UPDATE_DELAY = 300000; // 5 minutos (300.000 ms)

    async function fetchGraylogData(isAuto = false) {
        if (!isAuto) {
            showLoading('Buscando logs do Graylog...');
            startGlobalLoading();
        }
        
        try {
            const response = await fetch('/api/load-graylog', { method: 'POST' });

            if (!response.ok) {
                const error = await response.json();
                // Se falhar (ex: sem credenciais), para o auto-update para evitar spam de erros
                if (isAuto && autoUpdateInterval) {
                    toggleAutoUpdate(false);
                    showError(`Auto-update parado: ${error.detail}`);
                } else if (!isAuto) {
                    throw new Error(error.detail || 'Erro no servidor');
                }
                return;
            }

            const result = await response.json();
            if (!isAuto) showSuccess(result.message);
            
            await fetchAndRenderSummary();
            await loadFilters();
            
            // Atualiza a visualização atual se necessário (Investigação)
            const investigationPage = document.getElementById('investigation-page');
            if (investigationPage && investigationPage.style.display !== 'none') {
                if (isPatternView) {
                    fetchAndRenderPatterns();
                } else {
                    fetchAndRenderLogs();
                }
            }
        } catch (error) {
            if (!isAuto) showError(`Erro ao carregar do Graylog: ${error.message}`);
            else console.error("Erro no auto-update:", error);
        } finally {
            if (!isAuto) stopGlobalLoading();
        }
    }

    function toggleAutoUpdate(forceState = null) {
        const shouldStart = forceState !== null ? forceState : !autoUpdateInterval;
        const indicator = document.getElementById('auto-update-indicator');

        if (shouldStart) {
            if (autoUpdateInterval) clearInterval(autoUpdateInterval);
            // Executa imediatamente (mostrando loading na primeira vez)
            fetchGraylogData(false); 
            autoUpdateInterval = setInterval(() => fetchGraylogData(true), AUTO_UPDATE_DELAY);
            
            if (loadGraylogBtn) {
                loadGraylogBtn.textContent = "Stop Update Graylog (5m)";
                loadGraylogBtn.style.backgroundColor = "#d32f2f"; // Vermelho
            }
            if (indicator) indicator.style.display = 'inline-block';
        } else {
            if (autoUpdateInterval) {
                clearInterval(autoUpdateInterval);
                autoUpdateInterval = null;
            }
            if (loadGraylogBtn) {
                loadGraylogBtn.textContent = "Start Update Graylog";
                loadGraylogBtn.style.backgroundColor = ""; // Cor original
            }
            if (indicator) indicator.style.display = 'none';
        }
    }

    // Handler modificado para o botão (Toggle)
    if (loadGraylogBtn) {
        loadGraylogBtn.addEventListener('click', () => toggleAutoUpdate());
    }

    // Inicia automaticamente ao carregar a página
    toggleAutoUpdate(true);

    // Handler for mobile menu toggle
    if (menuToggleBtn && sidebar) {
        menuToggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('-translate-x-full');
        });
    }

    // Handler for Reset Filters
    if (resetFiltersBtn) {
        resetFiltersBtn.addEventListener('click', () => {
            // Reset state
            currentFilters = {
                search: "",
                level: "Todos",
                source: "Todos"
            };
            currentPage = 1;

            // 1. Limpa os inputs da aba Investigação
            const filterSearch = document.getElementById('filter-search');
            const filterLevel = document.getElementById('filter-level');
            const filterSource = document.getElementById('filter-source');
            
            if (filterSearch) filterSearch.value = "";
            if (filterLevel) filterLevel.value = "Todos";
            if (filterSource) filterSource.value = "Todos";

            // 2. Limpa os inputs da aba Monitoramento de API
            const apiSearchInput = document.getElementById('api-search-input');
            const apiSourceFilter = document.getElementById('api-source-filter');
            const apiStreamFilter = document.getElementById('api-stream-filter');
            if (apiSearchInput) apiSearchInput.value = "";
            if (apiSourceFilter) apiSourceFilter.value = "Todos";
            if (apiStreamFilter) apiStreamFilter.value = "Todos";

            // 3. Atualiza os dados da página que estiver ativa no momento
            const activePage = document.querySelector('.page-section.active');
            if (activePage && activePage.id === 'investigation-page') {
                if (isPatternView) {
                    fetchAndRenderPatterns();
                } else {
                    fetchAndRenderLogs();
                }
            } else if (activePage && activePage.id === 'api-monitoring-page') {
                loadApiData(); // Recarrega os gráficos da API zerados
            } else if (activePage && activePage.id === 'custom-metrics-page') {
                const metricSelect = document.getElementById('metric-visualize-select');
                if (metricSelect && metricSelect.value) {
                    loadMetricChart(metricSelect.value); // Recarrega gráfico de métrica sem filtro
                }
            }
            
            showSuccess("Todos os filtros globais foram limpos!");
        });
    }

    // Handler for Theme Toggle
    if (themeToggleBtn) {
        // Check local storage for saved theme
        if (localStorage.getItem('theme') === 'dark') {
            document.documentElement.classList.add('dark');
            themeToggleBtn.textContent = 'Modo Claro ☀️';
        }

        themeToggleBtn.addEventListener('click', () => {
            document.documentElement.classList.toggle('dark');
            
            if (document.documentElement.classList.contains('dark')) {
                localStorage.setItem('theme', 'dark');
                themeToggleBtn.textContent = 'Modo Claro ☀️';
            } else {
                localStorage.setItem('theme', 'light');
                themeToggleBtn.textContent = 'Modo Escuro 🌙';
            }
            // Atualiza a cor de todos os gráficos ativos
            updateChartsTheme();
        });
    }

    /**
     * Retorna um objeto de opções de tema para o Chart.js com base no modo atual (claro/escuro).
     */
    function getChartThemeOptions() {
        const isDarkMode = document.documentElement.classList.contains('dark');
        
        const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
        const textColor = isDarkMode ? '#cbd5e1' : '#334155'; // slate-300 e slate-700
        const tooltipBg = isDarkMode ? '#1e293b' : 'rgba(0, 0, 0, 0.8)';

        return {
            scales: {
                x: { ticks: { color: textColor }, grid: { color: gridColor } },
                y: { ticks: { color: textColor }, grid: { color: gridColor } }
            },
            plugins: {
                legend: { labels: { color: textColor } },
                tooltip: { backgroundColor: tooltipBg }
            }
        };
    }

    /**
     * Retorna uma paleta de cores para gráficos de pizza/doughnut com base no tema.
     */
    function getPieChartColors() {
        const isDarkMode = document.documentElement.classList.contains('dark');
        // Paletas com bom contraste para cada tema
        return isDarkMode 
            ? ['#38bdf8', '#fb923c', '#facc15', '#a78bfa', '#4ade80', '#f87171', '#94a3b8'] // Cores claras (sky, orange, yellow, violet, green, red, slate)
            : ['#0ea5e9', '#f97316', '#eab308', '#8b5cf6', '#22c55e', '#ef4444', '#64748b']; // Cores mais escuras
    }

    /**
     * Retorna uma paleta de cores para gráficos de barra com base no tema.
     */
    function getBarChartColors() {
        const isDarkMode = document.documentElement.classList.contains('dark');
        return {
            primary: isDarkMode ? '#60a5fa' : '#00529B', // blue-400 / lockton-blue
            secondary: isDarkMode ? '#a78bfa' : '#673ab7', // violet-400 / purple
            success: isDarkMode ? '#4ade80' : 'rgba(75, 192, 192, 0.6)', // green-400 / original teal
            error: isDarkMode ? '#f87171' : 'rgba(255, 99, 132, 0.6)', // red-400 / original red
        };
    }

    /**
     * Retorna uma paleta de cores para gráficos de linha com base no tema.
     */
    function getLineChartColors() {
        const isDarkMode = document.documentElement.classList.contains('dark');
        return {
            primary: {
                borderColor: isDarkMode ? '#60a5fa' : '#00529B', // blue-400 / lockton-blue
                backgroundColor: isDarkMode ? 'rgba(96, 165, 250, 0.1)' : 'rgba(0, 82, 155, 0.1)'
            },
            secondary: {
                borderColor: isDarkMode ? '#f97316' : '#ff9800', // orange-500 / orange
            },
            accent: {
                borderColor: isDarkMode ? '#c084fc' : '#9c27b0', // purple-400 / purple
                backgroundColor: isDarkMode ? 'rgba(192, 132, 252, 0.1)' : 'rgba(156, 39, 176, 0.1)'
            },
            dynamic: (index) => { // Para gráficos de infraestrutura
                const hue = (index * 137.508) % 360;
                const saturation = isDarkMode ? 70 : 60;
                const lightness = isDarkMode ? 60 : 45;
                return `hsla(${hue}, ${saturation}%, ${lightness}%, 1)`;
            }
        };
    }

    /**
     * Itera sobre todas as instâncias de gráfico ativas e atualiza suas cores de tema.
     */
    function updateChartsTheme() {
        const themeOptions = getChartThemeOptions();
        const pieColors = getPieChartColors();
        const pieBorderColor = document.documentElement.classList.contains('dark') ? '#1e293b' : '#ffffff'; // Cor de fundo do card
        const barColors = getBarChartColors();
        const lineColors = getLineChartColors();

        const allCharts = [
            volumeChart, forecastChart, rumVitalsChart, rumErrorsChart, 
            infraCpuChart, infraMemChart, infraDiskChart, apiStatusChart, 
            apiMethodChart, apiEndpointChart, cicdStatusChart, cicdDurationChart, 
            metricChart
        ];

        allCharts.forEach(chart => {
            if (chart && chart.options) {
                // Atualiza cores das escalas (eixos) e legendas para todos os gráficos de forma segura para não sobrescrever outras configs
                if (chart.options.scales?.x) {
                    if (chart.options.scales.x.ticks) chart.options.scales.x.ticks.color = themeOptions.scales.x.ticks.color;
                    if (chart.options.scales.x.grid) chart.options.scales.x.grid.color = themeOptions.scales.x.grid.color;
                }
                if (chart.options.scales?.y) {
                    if (chart.options.scales.y.ticks) chart.options.scales.y.ticks.color = themeOptions.scales.y.ticks.color;
                    if (chart.options.scales.y.grid) chart.options.scales.y.grid.color = themeOptions.scales.y.grid.color;
                }
                if (chart.options.plugins?.legend?.labels) {
                    chart.options.plugins.legend.labels.color = themeOptions.plugins.legend.labels.color;
                }
                if (chart.options.plugins?.tooltip) {
                    chart.options.plugins.tooltip.backgroundColor = themeOptions.plugins.tooltip.backgroundColor;
                }
                if (chart.options.plugins?.title) {
                    chart.options.plugins.title.color = themeOptions.plugins.legend.labels.color;
                }

                // Se for um gráfico de pizza/doughnut, atualiza as cores do dataset
                if (chart.config.type === 'pie' || chart.config.type === 'doughnut') {
                    chart.data.datasets.forEach(dataset => {
                        dataset.backgroundColor = pieColors;
                        dataset.borderColor = pieBorderColor;
                    });
                } else if (chart.config.type === 'bar') {
                    chart.data.datasets.forEach(dataset => {
                        switch(chart.canvas.id) {
                            case 'rum-vitals-chart':
                                dataset.backgroundColor = barColors.success;
                                break;
                            case 'rum-errors-chart':
                                dataset.backgroundColor = barColors.error;
                                break;
                            case 'api-endpoint-chart':
                                dataset.backgroundColor = barColors.secondary;
                                break;
                            default: // api-method-chart, cicd-duration-chart
                                dataset.backgroundColor = barColors.primary;
                                break;
                        }
                    });
                } else if (chart.config.type === 'line') {
                    chart.data.datasets.forEach((dataset, index) => {
                        switch(chart.canvas.id) {
                            case 'volume-chart':
                                dataset.borderColor = lineColors.primary.borderColor;
                                dataset.backgroundColor = lineColors.primary.backgroundColor;
                                break;
                            case 'forecast-chart':
                                if (dataset.label === 'Histórico') {
                                    dataset.borderColor = lineColors.primary.borderColor;
                                    dataset.backgroundColor = lineColors.primary.backgroundColor;
                                } else if (dataset.label === 'Previsão') {
                                    dataset.borderColor = lineColors.secondary.borderColor;
                                }
                                break;
                            case 'metric-chart':
                                dataset.borderColor = lineColors.accent.borderColor;
                                dataset.backgroundColor = lineColors.accent.backgroundColor;
                                break;
                            case 'infra-cpu-chart':
                            case 'infra-mem-chart':
                            case 'infra-disk-chart':
                                const dynamicColor = lineColors.dynamic(index);
                                dataset.borderColor = dynamicColor;
                                dataset.backgroundColor = dynamicColor;
                                break;
                        }
                    });
                }

                chart.update();
            }
        });
    }

    // Function to fetch summary data and update the UI
    async function fetchAndRenderSummary() {
        try {
            // 1. Carrega KPIs (Rápido)
            const summaryRes = await fetch('/api/data/summary');
            if (!summaryRes.ok) {
                const error = await summaryRes.json();
                throw new Error(error.detail || 'Erro ao buscar resumo de logs');
            }
            const summary = await summaryRes.json();
            updateDashboardKPIs(summary);

            // 2. Carrega Métricas de API (Médio - Async)
            fetch('/api/analysis/api-metrics')
                .then(res => res.ok ? res.json() : null)
                .then(apiMetrics => updateDashboardApiMetrics(apiMetrics))
                .catch(err => console.error("Erro API metrics:", err));

            // 3. Carrega Gráfico de Volume (Lento - Async)
            fetch('/api/data/volume-series')
                .then(res => res.ok ? res.json() : { time_series_volume: [] })
                .then(volumeData => {
                    // Proteção robusta contra dados nulos/indefinidos vindo da API
                    const series = (volumeData && volumeData.time_series_volume) ? volumeData.time_series_volume : [];
                    updateVolumeChart(series);
                })
                .catch(err => console.error("Erro Volume Chart:", err));

        } catch (error) {
            showError(error.message);
        }
    }

    function updateDashboardKPIs(summaryData) {
        document.getElementById('kpi-total-logs').textContent = summaryData.total_logs;
        document.getElementById('kpi-error-count').textContent = summaryData.error_count;
        document.getElementById('kpi-error-rate').textContent = `${summaryData.error_rate}%`;
        document.getElementById('kpi-unique-sources').textContent = summaryData.unique_sources;
    }

    function updateDashboardApiMetrics(apiMetricsData) {
        const avgLatencyEl = document.getElementById('kpi-avg-latency');
        const slowestListEl = document.getElementById('slowest-endpoints-list');

        if (apiMetricsData) {
            avgLatencyEl.textContent = `${apiMetricsData.stats.avg_latency} ms`;
            
            slowestListEl.innerHTML = '';
            if (apiMetricsData.slowest_endpoints.length > 0) {
                apiMetricsData.slowest_endpoints.slice(0, 5).forEach(ep => {
                    const li = document.createElement('li');
                    li.className = 'flex justify-between items-center p-1 -mx-1 rounded transition-colors';
                    li.innerHTML = `
                        <span class="truncate" title="${ep.endpoint}">${ep.endpoint}</span>
                        <span class="font-bold text-amber-600">${ep.p95_latency.toFixed(0)} ms</span>
                    `;
                    
                    if (ep.slowest_log && ep.slowest_log.message) {
                        li.classList.add('cursor-pointer', 'hover:bg-slate-100', 'dark:hover:bg-slate-800');
                        li.title = "Clique para ver o log da requisição mais lenta";
                        li.addEventListener('click', () => {
                            if (typeof openLogModal === 'function') {
                                openLogModal(ep.slowest_log);
                            }
                        });
                    }
                    
                    slowestListEl.appendChild(li);
                });
            } else {
                slowestListEl.innerHTML = '<li class="text-slate-400">Nenhuma métrica de latência encontrada.</li>';
            }
        } else {
            if(avgLatencyEl) avgLatencyEl.textContent = '--';
            if(slowestListEl) slowestListEl.innerHTML = '<li class="text-slate-400">Não foi possível carregar.</li>';
        }
    }

    function updateVolumeChart(timeSeriesData) {
        // Update Chart.js chart
        const canvas = document.getElementById('volume-chart');
        if (!canvas) return; // Proteção: Aborta se o elemento não existir no DOM (ex: troca rápida de aba)

        const ctx = canvas.getContext('2d');
        const lineColors = getLineChartColors();
        
        // Proteção contra dados nulos/indefinidos
        const data = timeSeriesData || [];

        const chartData = {
            labels: data.map(d => new Date(d.timestamp).toLocaleTimeString()),
            datasets: [{
                label: 'Volume de Logs',
                data: data.map(d => d.count),
                borderColor: lineColors.primary.borderColor,
                backgroundColor: lineColors.primary.backgroundColor,
                fill: true,
                tension: 0.1
            }]
        };
        
        const options = { responsive: true, maintainAspectRatio: false };
        Object.assign(options, getChartThemeOptions());
        
        options.plugins = options.plugins || {};
        options.plugins.legend = options.plugins.legend || {};
        options.plugins.legend.display = false; // Esconde a legenda padrão centralizada
        
        // Substitui a legenda pelo plugin de Título para garantir o alinhamento estrito à esquerda
        options.plugins.title = {
            display: true,
            text: 'Volume de Logs',
            align: 'start',
            color: getChartThemeOptions().plugins.legend.labels.color,
            font: { size: 14, weight: 'normal' },
            padding: { top: 0, bottom: 10 }
        };
        
        // Fallback de compatibilidade caso o Chart.js seja uma versão anterior (v2)
        options.legend = options.legend || {};
        options.legend.display = false;

        if (volumeChart) {
            volumeChart.options = options;
            volumeChart.data = chartData;
            volumeChart.update();
        } else {
            volumeChart = new Chart(ctx, {
                type: 'line',
                data: chartData,
                options: options
            });
        }
    }

    // --- Lógica de Navegação (SPA) ---
    const navLinks = document.querySelectorAll('.nav-link');
    const pageSections = document.querySelectorAll('.page-section');
    const pageTitle = document.getElementById('page-title');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Remove active class from all links and sections
            navLinks.forEach(l => l.classList.remove('active'));
            pageSections.forEach(s => {
                s.style.display = 'none';
                s.classList.remove('active');
            });

            // Add active class to clicked link
            link.classList.add('active');
            
            // Update page title
            if (pageTitle) {
                pageTitle.textContent = link.querySelector('span').textContent;
            }

            // Hide sidebar on mobile after navigation
            if (sidebar && window.innerWidth < 1024) {
                sidebar.classList.add('-translate-x-full');
            }

            // Show target section
            const targetId = link.getAttribute('data-target');
            
            // Atualiza a URL com o hash da página (sem recarregar a tela)
            const pageHash = targetId.replace('-page', '');
            if (window.location.hash !== '#' + pageHash) {
                history.pushState(null, '', '#' + pageHash);
            }

            const targetSection = document.getElementById(targetId);
            if (targetSection) {
                targetSection.style.display = 'block';
                targetSection.classList.add('active');
                
                // Se for a página de investigação, carrega os logs
                if (targetId === 'investigation-page') {
                    if (isPatternView) {
                        fetchAndRenderPatterns();
                    } else {
                        fetchAndRenderLogs();
                    }
                } else if (targetId === 'intelligence-page') {
                    loadIntelligenceData();
                } else if (targetId === 'custom-metrics-page') {
                    loadMetricsList();
                } else if (targetId === 'rum-page') {
                    loadRumData();
                } else if (targetId === 'infrastructure-page') {
                    loadInfrastructureData();
                } else if (targetId === 'api-monitoring-page') {
                    loadApiData();
                } else if (targetId === 'cicd-page') {
                    loadCicdData();
                } else if (targetId === 'streams-page') {
                    loadStreamsData();
                } else if (targetId === 'alerts-page') {
                    loadAlertsData();
                } else if (targetId === 'tools-page') {
                    // Nenhuma carga inicial necessária
                }
            }
        });
    });

    // --- Roteamento via Hash da URL (SPA Routing) ---
    function handleRouting() {
        const hash = window.location.hash.replace('#', '');
        if (hash) {
            const targetLink = Array.from(navLinks).find(l => l.getAttribute('data-target') === `${hash}-page`);
            if (targetLink && !targetLink.classList.contains('active')) {
                targetLink.click();
            }
        } else if (navLinks.length > 0) {
            // Se não tiver hash na URL (acesso à raiz), redireciona visualmente para a primeira aba
            if (!navLinks[0].classList.contains('active')) {
                navLinks[0].click();
                history.replaceState(null, '', '#' + navLinks[0].getAttribute('data-target').replace('-page', ''));
            }
        }
    }

    // Escuta eventos de Voltar/Avançar do navegador e executa o roteamento na carga inicial da página
    window.addEventListener('popstate', handleRouting);
    handleRouting();

    // --- Lógica da Página de Investigação ---
    
    async function loadFilters() {
        try {
            const response = await fetch('/api/data/filters');
            if (!response.ok) return;
            const data = await response.json();
            
            const levelSelect = document.getElementById('filter-level');
            const sourceSelect = document.getElementById('filter-source');
            
            // Limpa e repopula (mantendo a opção 'Todos')
            levelSelect.innerHTML = '<option value="Todos">Todos</option>';
            sourceSelect.innerHTML = '<option value="Todos">Todos</option>';
            
            data.levels.forEach(lvl => {
                const opt = document.createElement('option');
                opt.value = lvl;
                opt.textContent = lvl;
                levelSelect.appendChild(opt);
            });
            
            data.sources.forEach(src => {
                const opt = document.createElement('option');
                opt.value = src;
                opt.textContent = src;
                sourceSelect.appendChild(opt);
            });
        } catch (e) {
            console.error("Erro ao carregar filtros", e);
        }
    }

    async function fetchAndRenderLogs() {
        startGlobalLoading();
        const tbody = document.querySelector('#logs-table tbody');
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Carregando...</td></tr>';
        
        const params = new URLSearchParams({
            page: currentPage,
            limit: 20,
            search: currentFilters.search,
            level: currentFilters.level,
            source: currentFilters.source,
            sort: 'desc'
        });

        try {
            const response = await fetch(`/api/data/logs?${params}`);
            const data = await response.json();
            
            tbody.innerHTML = '';
            
            if (data.data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Nenhum log encontrado.</td></tr>';
            } else {
                data.data.forEach(log => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${log.timestamp}</td>
                        <td>${log.log_level}</td>
                        <td>${log.source}</td>
                        <td style="word-break: break-all;">${log.message.substring(0, 200)}${log.message.length > 200 ? '...' : ''}</td>
                    `;
                    tr.addEventListener('click', () => openLogModal(log));
                    tbody.appendChild(tr);
                });
            }
            
            document.getElementById('page-info').textContent = `Página ${data.page} de ${data.pages}`;
            document.getElementById('prev-page').disabled = data.page <= 1;
            document.getElementById('next-page').disabled = data.page >= data.pages;
            
        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="4" style="color:red;">Erro ao carregar logs: ${error.message}</td></tr>`;
        } finally {
            stopGlobalLoading();
        }
    }

    // --- Lógica de Padrões (Clusters) ---
    const toggleViewBtn = document.getElementById('toggle-view-mode');
    const logsStreamContainer = document.getElementById('logs-stream-container');
    const logsPatternsContainer = document.getElementById('logs-patterns-container');

    if (toggleViewBtn) {
        toggleViewBtn.addEventListener('click', () => {
            isPatternView = !isPatternView;
            if (isPatternView) {
                toggleViewBtn.textContent = "Alternar para Lista";
                logsStreamContainer.style.display = 'none';
                logsPatternsContainer.style.display = 'block';
                fetchAndRenderPatterns();
            } else {
                toggleViewBtn.textContent = "Alternar para Padrões";
                logsStreamContainer.style.display = 'block';
                logsPatternsContainer.style.display = 'none';
                fetchAndRenderLogs();
            }
        });
    }

    async function fetchAndRenderPatterns() {
        startGlobalLoading();
        const tbody = document.querySelector('#patterns-table tbody');
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Carregando padrões...</td></tr>';

        const params = new URLSearchParams({
            search: currentFilters.search,
            level: currentFilters.level,
            source: currentFilters.source
        });

        try {
            const response = await fetch(`/api/analysis/patterns?${params}`);
            const data = await response.json();
            
            tbody.innerHTML = '';
            if (data.patterns.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Nenhum padrão encontrado.</td></tr>';
            } else {
                data.patterns.forEach(p => {
                    tbody.innerHTML += `<tr>
                        <td>${p.count}</td>
                        <td>${p.percent.toFixed(2)}%</td>
                        <td>${p.log_level}</td>
                        <td style="word-break: break-all; font-family: monospace; font-size: 0.9em;">${p.signature.substring(0, 150)}...</td>
                    </tr>`;
                });
            }
        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="4" style="color:red;">Erro: ${error.message}</td></tr>`;
        } finally {
            stopGlobalLoading();
        }
    }

    // --- Lógica do Mapa de Serviços ---
    const btnShowMap = document.getElementById('btn-show-map');
    const btnCloseMap = document.getElementById('btn-close-map');
    const mapContainer = document.getElementById('service-map-container');
    let network = null;

    if (btnShowMap) {
        btnShowMap.addEventListener('click', () => {
            mapContainer.style.display = 'block';
            fetchAndRenderServiceMap();
        });
    }

    if (btnCloseMap) {
        btnCloseMap.addEventListener('click', () => {
            mapContainer.style.display = 'none';
        });
    }

    async function fetchAndRenderServiceMap() {
        startGlobalLoading();
        const mapDiv = document.getElementById('service-map');
        mapDiv.innerHTML = '<p style="text-align:center; padding-top:200px;">Carregando mapa...</p>';

        const params = new URLSearchParams({
            search: currentFilters.search,
            level: currentFilters.level,
            source: currentFilters.source
        });

        try {
            const response = await fetch(`/api/analysis/dependencies?${params}`);
            const data = await response.json();
            
            if (data.edges.length === 0) {
                mapDiv.innerHTML = '<p style="text-align:center; padding-top:200px;">Nenhuma dependência encontrada com os filtros atuais.</p>';
                return;
            }

            // Processa Nós e Arestas
            const nodesSet = new Set();
            const edges = [];

            data.edges.forEach(edge => {
                nodesSet.add(edge.source);
                nodesSet.add(edge.target);
                edges.push({
                    from: edge.source,
                    to: edge.target,
                    label: String(edge.count),
                    arrows: 'to',
                    value: edge.count // Espessura baseada na contagem
                });
            });

            const nodes = Array.from(nodesSet).map((id, index) => ({
                id: id,
                label: id,
                shape: 'box',
                color: { background: '#4caf50', border: '#388e3c' },
                font: { color: 'white' }
            }));

            // Renderiza com Vis.js
            const visData = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };
            const options = { physics: { stabilization: true } };
            network = new vis.Network(mapDiv, visData, options);

        } catch (e) {
            mapDiv.innerHTML = `<p style="text-align:center; color:red; padding-top:200px;">Erro: ${e.message}</p>`;
        } finally {
            stopGlobalLoading();
        }
    }

    // --- Lógica do Explorador de Traces ---
    const btnShowTraces = document.getElementById('btn-show-traces');
    const btnCloseTrace = document.getElementById('btn-close-trace');
    const traceContainer = document.getElementById('trace-explorer-container');
    const traceSelect = document.getElementById('trace-select');
    let traceChart = null;

    if (btnShowTraces) {
        btnShowTraces.addEventListener('click', async () => {
            traceContainer.style.display = 'block';
            await loadTracesList();
        });
    }

    if (btnCloseTrace) {
        btnCloseTrace.addEventListener('click', () => {
            traceContainer.style.display = 'none';
        });
    }

    if (traceSelect) {
        traceSelect.addEventListener('change', () => {
            const traceId = traceSelect.value;
            if (traceId) loadTraceGantt(traceId);
        });
    }

    async function loadTracesList() {
        startGlobalLoading();
        traceSelect.innerHTML = '<option value="">Carregando traces...</option>';
        const params = new URLSearchParams({
            search: currentFilters.search,
            level: currentFilters.level,
            source: currentFilters.source
        });

        try {
            const response = await fetch(`/api/analysis/traces?${params}`);
            const data = await response.json();
            
            traceSelect.innerHTML = '<option value="">Selecione um Trace ID...</option>';
            if (data.traces.length === 0) {
                const opt = document.createElement('option');
                opt.textContent = "Nenhum trace encontrado com os filtros atuais.";
                traceSelect.appendChild(opt);
                return;
            }

            data.traces.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.trace_id;
                const time = new Date(t.start_time).toLocaleTimeString();
                opt.textContent = `${time} | ${t.trace_id} | ${t.duration_ms.toFixed(0)}ms | ${t.error_count} Erros`;
                traceSelect.appendChild(opt);
            });
        } catch (e) {
            traceSelect.innerHTML = '<option value="">Erro ao carregar traces</option>';
        } finally {
            stopGlobalLoading();
        }
    }

    async function loadTraceGantt(traceId) {
        startGlobalLoading();
        try {
            const response = await fetch(`/api/analysis/trace/${traceId}`);
            const data = await response.json();
            
            const ctx = document.getElementById('trace-gantt-chart').getContext('2d');
            if (traceChart) traceChart.destroy();

            const sources = [...new Set(data.events.map(e => e.source))];
            
            const eventsData = data.events.map(e => ({
                x: [new Date(e.start).getTime(), new Date(e.end).getTime()],
                y: e.source,
                message: e.message,
                status: e.status
            }));

            traceChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: sources,
                    datasets: [{
                        label: 'Eventos',
                        data: eventsData,
                        backgroundColor: ctx => ctx.raw.status === 'Error' ? 'rgba(244, 67, 54, 0.7)' : 'rgba(76, 175, 80, 0.7)',
                        borderWidth: 1
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            min: Math.min(...data.events.map(e => new Date(e.start).getTime())),
                            ticks: { callback: val => new Date(val).toLocaleTimeString() }
                        }
                    },
                    plugins: {
                        tooltip: {
                            callbacks: {
                                label: ctx => {
                                    const d = ctx.raw;
                                    const dur = d.x[1] - d.x[0];
                                    return `${d.message} (${dur}ms)`;
                                }
                            }
                        }
                    }
                }
            });
        } catch (e) {
            console.error("Erro Trace Gantt", e);
        } finally {
            stopGlobalLoading();
        }
    }

    // --- Lógica do Modal ---

    async function performInitialAnalysis() {
        // Desabilita o input enquanto a análise inicial ocorre
        chatInput.disabled = true;
        chatSendBtn.disabled = true;

        // Mostra a mensagem de carregamento
        chatHistoryDiv.innerHTML = ''; // Limpa qualquer conteúdo anterior
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'chat-message assistant';
        loadingDiv.innerHTML = '<span class="italic text-slate-400">Analisando o log...</span>';
        chatHistoryDiv.appendChild(loadingDiv);

        // O prompt do sistema já está em currentChatMessages.
        // Adicionamos uma pergunta inicial para guiar a IA.
        const initialUserMessage = "Faça uma análise inicial e concisa deste log, destacando os pontos mais importantes.";
        const messagesForAnalysis = [
            ...currentChatMessages,
            { role: "user", content: initialUserMessage }
        ];

        try {
            const response = await fetch('/api/analysis/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: messagesForAnalysis })
            });
            const data = await response.json();
            
            chatHistoryDiv.removeChild(loadingDiv);
            appendChatMessage("assistant", data.response);
            
            // Atualiza o histórico de chat para incluir a pergunta e a resposta iniciais
            currentChatMessages = messagesForAnalysis;
            currentChatMessages.push({ role: "assistant", content: data.response });
            
        } catch (e) {
            chatHistoryDiv.removeChild(loadingDiv);
            appendChatMessage("assistant", "Desculpe, ocorreu um erro ao tentar analisar o log.");
        } finally {
            // Reabilita o input para o usuário poder conversar
            chatInput.disabled = false;
            chatSendBtn.disabled = false;
            chatInput.focus();
        }
    }

    async function openLogModal(log) {
        // Limpa conteúdo anterior
        modalContent.innerHTML = '';
        const actionsContainer = document.getElementById('modal-actions-container');
        if (actionsContainer) actionsContainer.innerHTML = '';

        chatInput.value = '';
        
        // Reset Context Section
        const contextContainer = document.getElementById('modal-context-logs');
        const contextTbody = document.querySelector('#context-table tbody');
        const btnLoadContext = document.getElementById('btn-load-context');
        const btnLoadContextText = btnLoadContext ? btnLoadContext.querySelector('.btn-load-context-text') : null;
        
        if (contextContainer) contextContainer.style.display = 'none';
        if (contextTbody) contextTbody.innerHTML = '';
        if (btnLoadContext) {
            if (btnLoadContextText) btnLoadContextText.textContent = "Carregar Contexto";
            btnLoadContext.disabled = false;
            
            // Define click handler for this specific log
            btnLoadContext.onclick = async () => {
                if (btnLoadContextText) btnLoadContextText.textContent = "Carregando...";
                btnLoadContext.disabled = true;
                
                try {
                    const params = new URLSearchParams({
                        timestamp: log.timestamp,
                        source: log.source,
                        window: 300 // 5 minutos
                    });
                    
                    const response = await fetch(`/api/data/context?${params}`);
                    const data = await response.json();
                    
                    contextTbody.innerHTML = '';
                    if (data.logs.length === 0) {
                        contextTbody.innerHTML = '<tr><td colspan="3" style="text-align:center;">Nenhum log vizinho encontrado.</td></tr>';
                    } else {
                        // Ordena os logs de contexto do mais recente para o mais antigo
                        data.logs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                        data.logs.forEach(ctxLog => {
                            // Tenta destacar o log atual (comparação simples de string)
                            const isTarget = ctxLog.timestamp == log.timestamp && ctxLog.message == log.message;
                            const rowStyle = isTarget ? 'background-color: rgba(255, 235, 59, 0.3); font-weight: bold;' : '';
                            
                            // Formata hora
                            const timeStr = new Date(ctxLog.timestamp).toLocaleTimeString();
                            
                            contextTbody.innerHTML += `<tr style="${rowStyle}">
                                <td style="white-space: nowrap;">${timeStr}</td>
                                <td>${ctxLog.log_level}</td>
                                <td style="word-break: break-all; font-size: 0.9em;">${ctxLog.message.substring(0, 150)}...</td>
                            </tr>`;
                        });
                    }
                    contextContainer.style.display = 'block';
                } catch (e) {
                    contextTbody.innerHTML = `<tr><td colspan="3" style="color:red">Erro: ${e.message}</td></tr>`;
                    contextContainer.style.display = 'block';
                } finally {
                    if (btnLoadContextText) btnLoadContextText.textContent = "Carregar Contexto";
                    btnLoadContext.disabled = false;
                }
            };
        }

        // Busca o prompt inicial do backend para o chat
        try {
            const response = await fetch('/api/analysis/initial-prompt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    timestamp: log.timestamp,
                    source: log.source,
                    message: log.message
                })
            });
            if (!response.ok) throw new Error('Falha ao buscar prompt inicial da IA.');
            const data = await response.json();
            
            currentChatMessages = [{ role: "system", content: data.prompt }];
        } catch (e) {
            console.error("Erro ao buscar prompt inicial:", e);
            // Fallback para um prompt genérico em caso de erro
            currentChatMessages = [{ role: "system", content: "Você é um assistente SRE especialista. Ocorreu um erro ao carregar o contexto do log." }];
            chatHistoryDiv.innerHTML = '<div class="text-slate-400 italic text-center p-3 text-red-500">Erro ao contatar a IA.</div>';
        }

        // Dispara a análise inicial automática
        performInitialAnalysis();

        // Helper para criar linhas de detalhe
        const createDetailLine = (label, value) => {
            const div = document.createElement('div');
            div.style.marginBottom = '8px';
            div.innerHTML = `<strong>${label}:</strong> <span>${value || 'N/A'}</span>`;
            return div;
        };

        modalContent.appendChild(createDetailLine('Timestamp', log.timestamp));
        modalContent.appendChild(createDetailLine('Level', log.log_level));
        modalContent.appendChild(createDetailLine('Source', log.source));
        modalContent.appendChild(createDetailLine('Category', log.category));
        
        const msgHeader = document.createElement('div');
        msgHeader.innerHTML = '<strong>Message:</strong>';
        msgHeader.style.marginTop = '15px';
        modalContent.appendChild(msgHeader);

        const msgPre = document.createElement('div');
        msgPre.textContent = log.message; // Usa textContent para segurança contra XSS
        msgPre.style.marginTop = '5px';
        msgPre.className = 'text-slate-700 dark:text-slate-300 whitespace-pre-wrap';
        modalContent.appendChild(msgPre);

        // Adiciona botão para criar Ticket no Jira no rodapé do modal
        if (actionsContainer) {
            const jiraBtn = document.createElement('button');
            jiraBtn.className = "px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium transition-colors flex items-center gap-2 shadow-sm";
            jiraBtn.innerHTML = "🎫 Criar Ticket Jira"; // Mantém o emoji ou use ícone se preferir
            
            jiraBtn.onclick = () => {
                const summary = `[Investigação] ${log.source} - ${log.log_level}`;
                let description = `Timestamp: ${log.timestamp}\nLevel: ${log.log_level}\nSource: ${log.source}\nCategory: ${log.category}\n\nMessage:\n${log.message}`;
                
                // Verifica se há análise da IA disponível no histórico (pega a última resposta do assistente)
                if (currentChatMessages && currentChatMessages.length > 0) {
                    const lastAiMsg = [...currentChatMessages].reverse().find(m => m.role === 'assistant');
                    if (lastAiMsg && lastAiMsg.content) {
                        description += `\n\n--- Análise da IA ---\n${lastAiMsg.content}`;
                    }
                }

                openJiraModalWithData(summary, description);
            };
            actionsContainer.appendChild(jiraBtn);
        }

        logModal.style.display = "flex";
    }

    // --- Lógica de Envio do Chat ---
    async function sendChatMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        // Adiciona mensagem do usuário na UI e no histórico
        appendChatMessage("user", text);
        currentChatMessages.push({ role: "user", content: text });
        chatInput.value = '';

        // Mostra loading
        const loadingDiv = document.createElement('div');
        loadingDiv.textContent = "Digitando...";
        loadingDiv.style.color = "#888";
        loadingDiv.style.fontSize = "0.8em";
        chatHistoryDiv.appendChild(loadingDiv);
        chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight;

        try {
            const response = await fetch('/api/analysis/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: currentChatMessages })
            });
            const data = await response.json();
            
            chatHistoryDiv.removeChild(loadingDiv);
            appendChatMessage("assistant", data.response);
            currentChatMessages.push({ role: "assistant", content: data.response });
            
        } catch (e) {
            chatHistoryDiv.removeChild(loadingDiv);
            appendChatMessage("assistant", "Erro ao conectar com a IA.");
        }
    }

    function appendChatMessage(role, text) {
        const div = document.createElement('div');
        div.className = `chat-message ${role}`;
        // Converte quebras de linha para <br>
        div.innerHTML = text.replace(/\n/g, '<br>');
        chatHistoryDiv.appendChild(div);
        chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight;
    }

    if (chatSendBtn) chatSendBtn.addEventListener('click', sendChatMessage);
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendChatMessage();
        });
    }

    if (closeModalSpan) closeModalSpan.onclick = () => logModal.style.display = "none";
    window.onclick = (event) => { if (event.target == logModal) logModal.style.display = "none"; };

    // Event Listeners para Filtros e Paginação
    const btnSearch = document.getElementById('btn-search');
    if (btnSearch) {
        btnSearch.addEventListener('click', async () => {
            const btnIcon = btnSearch.querySelector('.btn-search-icon');
            const btnText = btnSearch.querySelector('.btn-search-text');

            // Disable button and show loading state
            btnSearch.disabled = true;
            btnText.textContent = 'Buscando';
            btnIcon.innerHTML = '<i data-lucide="loader-2" class="animate-spin w-4 h-4"></i>';
            lucide.createIcons({ nodes: [btnIcon.querySelector('i')] });

            try {
                currentFilters.search = document.getElementById('filter-search').value;
                currentFilters.level = document.getElementById('filter-level').value;
                currentFilters.source = document.getElementById('filter-source').value;
                currentPage = 1;
                if (isPatternView) {
                    await fetchAndRenderPatterns();
                } else {
                    await fetchAndRenderLogs();
                }
            } finally {
                // Re-enable button and restore original state
                btnSearch.disabled = false;
                btnText.textContent = 'Buscar';
                btnIcon.innerHTML = '';
            }
        });
    }

    const btnPrevPage = document.getElementById('prev-page');
    if (btnPrevPage) {
        btnPrevPage.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                fetchAndRenderLogs();
            }
        });
    }

    const btnNextPage = document.getElementById('next-page');
    if (btnNextPage) {
        btnNextPage.addEventListener('click', () => {
            currentPage++;
            fetchAndRenderLogs();
        });
    }

    // Event Listener para Exportação
    const btnExportCsv = document.getElementById('btn-export-csv');
    if (btnExportCsv) {
        btnExportCsv.addEventListener('click', () => {
            const params = new URLSearchParams({
                search: currentFilters.search,
                level: currentFilters.level,
                source: currentFilters.source
            });

            const exportUrl = `/api/data/export?${params}`;
            
            // Abre a URL, o que forçará o download devido aos headers 'Content-Disposition'
            window.open(exportUrl, '_blank');
        });
    }

    // --- Lógica da Página de Inteligência ---

    async function loadIntelligenceData() {
        startGlobalLoading();
        try {
            await Promise.all([
                fetchForecast(),
                fetchAnomalies(),
                fetchSecurityThreats()
            ]);
        } finally {
            stopGlobalLoading();
        }
    }

    async function fetchForecast() {
        try {
            const response = await fetch('/api/analysis/forecast');
            if (!response.ok) return;
            const data = await response.json();
            
            document.getElementById('forecast-trend').textContent = `Tendência: ${data.trend}`;
            const lineColors = getLineChartColors();
            
            const ctx = document.getElementById('forecast-chart').getContext('2d');
            const labels = data.data.map(d => new Date(d.timestamp).toLocaleTimeString());
            // Separa dados históricos e previstos baseados na string 'type' retornada pelo backend
            const historical = data.data.map(d => d.type.includes('Histórico') ? d.count : null);
            const forecast = data.data.map(d => d.type.includes('Previsão') ? d.count : null);
            
            if (forecastChart) forecastChart.destroy();
            
            const options = { responsive: true, maintainAspectRatio: false };
            Object.assign(options, getChartThemeOptions());

            forecastChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Histórico',
                            data: historical,
                            borderColor: lineColors.primary.borderColor,
                            backgroundColor: lineColors.primary.backgroundColor,
                            fill: true,
                            tension: 0.1
                        },
                        {
                            label: 'Previsão',
                            data: forecast,
                            borderColor: lineColors.secondary.borderColor,
                            borderDash: [5, 5],
                            fill: false,
                            tension: 0.1
                        }
                    ]
                },
                options: options
            });
            
        } catch (e) {
            console.error("Erro forecast", e);
        }
    }

    async function fetchAnomalies() {
        const list = document.getElementById('anomalies-list');
        try {
            const response = await fetch('/api/analysis/anomalies');
            if (!response.ok) {
                list.innerHTML = '<li>Aguardando dados...</li>';
                return;
            }
            const data = await response.json();
            
            list.innerHTML = '';
            if (data.anomalies.length === 0) {
                list.innerHTML = '<li style="color: green">Nenhuma anomalia detectada.</li>';
            } else {
                data.anomalies.forEach(a => {
                    const li = document.createElement('li');
                    li.textContent = `${new Date(a.timestamp).toLocaleString()}: Volume anormal (${a.count} logs)`;
                    list.appendChild(li);
                });
            }
        } catch (e) {
            list.innerHTML = '<li>Erro ao carregar anomalias.</li>';
        }
    }

    async function fetchSecurityThreats() {
        const tbody = document.querySelector('#security-table tbody');
        try {
            const response = await fetch('/api/analysis/security');
            if (!response.ok) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#64748b;">Aguardando dados...</td></tr>';
                return;
            }
            const data = await response.json();
            
            tbody.innerHTML = '';
            if (data.threats.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#64748b;">Nenhuma ameaça detectada.</td></tr>';
            } else {
                data.threats.forEach(t => {
                    tbody.innerHTML += `<tr>
                        <td>${t.ip}</td>
                        <td>${t.status}</td>
                        <td>${t.total_logs}</td>
                        <td>${(t.error_rate * 100).toFixed(1)}%</td>
                    </tr>`;
                });
            }
        } catch (e) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#64748b;">Erro ao carregar segurança.</td></tr>';
        }
    }

    const btnClearLoadTest = document.getElementById('btn-clear-load-test');
    if (btnClearLoadTest) {
        btnClearLoadTest.addEventListener('click', () => {
            const container = document.getElementById('load-test-results-container');
            if(container) {
                container.innerHTML = '<p class="text-slate-500 dark:text-slate-400">Resultados do teste aparecerão aqui.</p>';
            }
        });
    }

    const btnRunAi = document.getElementById('run-ai-btn');
    if (btnRunAi) {
        btnRunAi.addEventListener('click', async () => {
        const container = document.getElementById('ai-results-container');
        container.innerHTML = '<p style="text-align:center; color:#64748b;">Processando análise de IA... (Isso pode levar alguns segundos)</p>';
        
        try {
            const response = await fetch('/api/analysis/ai', { method: 'POST' });
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Erro ao processar análise.');
            }

            container.innerHTML = '';
            if (!data.analysis || data.analysis.length === 0) {
                container.innerHTML = '<p style="text-align:center;">Nenhum erro crítico encontrado para análise.</p>';
                return;
            }
            
            data.analysis.forEach(item => {
                // Tenta extrair dados do Jira da resposta
                const jiraData = extractJiraData(item.analysis);
                let jiraBtnHtml = '';
                
                // Se encontrou dados de ticket, adiciona o botão
                if (jiraData) {
                    // Escapa aspas duplas para usar em atributos de dados de forma segura
                    const safeSummary = jiraData.summary.replace(/"/g, '&quot;');
                    const safeDesc = jiraData.description.replace(/"/g, '&quot;');
                    jiraBtnHtml = `<div style="margin-top:10px;"><button class="jira-btn" data-summary="${safeSummary}" data-description="${safeDesc}">🎫 Criar Ticket Jira</button></div>`;
                }

                const div = document.createElement('div');
                div.className = 'ai-analysis-card';
                div.innerHTML = `
                    <div class="ai-analysis-header">
                        ${new Date(item.timestamp).toLocaleString()} | ${item.message.substring(0, 100)}...
                    </div>
                    <div class="ai-analysis-content">${item.analysis.replace(/\n/g, '<br>')}</div>
                    ${jiraBtnHtml}
                `;
                container.appendChild(div);
            });
            
        } catch (e) {
            container.innerHTML = `<p style="color:red">Erro na análise: ${e.message}</p>`;
        }
    });
    }

    // --- Lógica de Integração Jira ---

    // Função para extrair Título e Descrição da resposta da IA
    function extractJiraData(text) {
        if (!text.includes("TICKET JIRA")) return null;

        let summary = "";
        let description = "";

        // Regex simples para capturar Título e Descrição baseados no prompt padrão
        const summaryMatch = text.match(/(?:Título|Summary|Titulo)[:\s*]+(.*?)(?:\n|$)/i);
        const descMatch = text.match(/(?:Descrição|Description|Descricao)[:\s*]+([\s\S]*?)(?:Prioridade|$)/i);

        if (summaryMatch) summary = summaryMatch[1].trim();
        if (descMatch) description = descMatch[1].trim();

        // Fallback se a regex falhar mas tiver a seção
        if (!summary) summary = "Análise de Incidente (Log Analytics)";
        if (!description) description = text;

        return { summary, description };
    }

    // Função para abrir o modal do Jira com os dados
    function openJiraModalWithData(summary, description) {
        document.getElementById('jira-ticket-summary').value = summary;
        document.getElementById('jira-ticket-desc').value = description;
        document.getElementById('jira-ticket-email').value = ""; // Limpa ou poderia pegar de localStorage
        jiraStatus.textContent = "";
        
        jiraModal.style.display = "flex";
    }

    // Adiciona um listener de eventos no container dos resultados da IA (Event Delegation)
    // Isso é mais robusto do que usar `onclick` em HTML dinâmico.
    const aiResultsContainer = document.getElementById('ai-results-container');
    if (aiResultsContainer) {
        aiResultsContainer.addEventListener('click', (e) => {
            // Usa .closest() para encontrar o botão, mesmo que o clique seja em um filho (ícone)
            const jiraButton = e.target.closest('.jira-btn');
            if (jiraButton) {
                // Pega os dados dos atributos data-*
                const summary = jiraButton.dataset.summary;
                const description = jiraButton.dataset.description;
                openJiraModalWithData(summary, description);
            }
        });
    }

    if (closeJiraModal) closeJiraModal.onclick = () => jiraModal.style.display = "none";
    
    // Fecha modais ao clicar fora
    window.onclick = (event) => { 
        if (event.target == logModal) logModal.style.display = "none"; 
        if (event.target == jiraModal) jiraModal.style.display = "none";
    };

    if (btnSubmitJira) {
        btnSubmitJira.addEventListener('click', async () => {
            const email = document.getElementById('jira-ticket-email').value;
            const summary = document.getElementById('jira-ticket-summary').value;
            const desc = document.getElementById('jira-ticket-desc').value;

            if (!email || !summary) {
                alert("Preencha Email e Título.");
                return;
            }

            jiraStatus.textContent = "Enviando...";
            jiraStatus.style.color = "#333";

            const formData = new FormData();
            formData.append('email', email);
            formData.append('summary', summary);
            formData.append('description', desc);

            try {
                const response = await fetch('/api/integrations/jira/create', { method: 'POST', body: formData });
                const data = await response.json();
                
                if (!response.ok) throw new Error(data.detail);
                
                jiraStatus.textContent = "✅ Ticket criado com sucesso!";
                jiraStatus.style.color = "green";
                setTimeout(() => jiraModal.style.display = "none", 2000);
            } catch (e) {
                jiraStatus.textContent = `Erro: ${e.message}`;
                jiraStatus.style.color = "red";
            }
        });
    }

    // --- Lógica da Página de Métricas Customizadas ---

    const btnTestRegex = document.getElementById('test-regex-btn');
    if (btnTestRegex) {
        btnTestRegex.addEventListener('click', async () => {
        const regex = document.getElementById('regex-input').value;
        const resultsDiv = document.getElementById('regex-results');
        
        if (!regex) {
            resultsDiv.innerHTML = '<p style="color:red">Digite uma regex.</p>';
            return;
        }
        
        resultsDiv.innerHTML = '<p>Testando...</p>';
        
        const formData = new FormData();
        formData.append('regex', regex);
        
        try {
            const response = await fetch('/api/metrics/test', { method: 'POST', body: formData });
            const data = await response.json();
            
            if (!response.ok) throw new Error(data.detail);
            
            let html = `<p><strong>${data.count}</strong> logs correspondem a esta regex.</p>`;
            
            if (data.preview.length > 0) {
                html += '<h5>Exemplos (Top 5):</h5><ul class="anomalies-list">';
                data.preview.forEach(item => {
                    const matchesStr = item.matches.length > 0 ? `Matches: [${item.matches.join(', ')}]` : '';
                    html += `<li><small>${item.timestamp}</small><br>${item.message.substring(0, 100)}... <br><strong>${matchesStr}</strong></li>`;
                });
                html += '</ul>';
            }
            
            resultsDiv.innerHTML = html;
        } catch (e) {
            resultsDiv.innerHTML = `<p style="color:red">Erro: ${e.message}</p>`;
        }
    });
    }

    const btnSaveMetric = document.getElementById('save-metric-btn');
    if (btnSaveMetric) {
        btnSaveMetric.addEventListener('click', async () => {
        const name = document.getElementById('metric-name').value;
        const regex = document.getElementById('regex-input').value;
        const type = document.getElementById('metric-type').value;
        
        if (!name || !regex) {
            alert("Preencha nome e regex.");
            return;
        }
        
        const formData = new FormData();
        formData.append('name', name);
        formData.append('regex', regex);
        formData.append('metric_type', type);
        
        try {
            const response = await fetch('/api/metrics', { method: 'POST', body: formData });
            if (response.ok) {
                alert("Métrica salva!");
                document.getElementById('metric-name').value = '';
                loadMetricsList();
            } else {
                alert("Erro ao salvar.");
            }
        } catch (e) {
            console.error(e);
        }
    });
    }

    // Listener para seleção de métrica para visualização
    const metricSelect = document.getElementById('metric-visualize-select');
    if (metricSelect) {
        metricSelect.addEventListener('change', () => {
            const id = metricSelect.value;
            if (id) {
                loadMetricChart(id);
            } else {
                if (metricChart) metricChart.destroy();
                document.getElementById('metric-stats').innerHTML = '';
            }
        });
    }

    async function loadMetricsList() {
        startGlobalLoading();
        const tbody = document.querySelector('#metrics-table tbody');
        tbody.innerHTML = '<tr><td colspan="4">Carregando...</td></tr>';
        
        try {
            const response = await fetch('/api/metrics');
            const metrics = await response.json();
            
            // Atualiza Tabela
            tbody.innerHTML = '';
            if (metrics.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4">Nenhuma métrica definida.</td></tr>';
                return;
            }
            
            metrics.forEach(m => {
                tbody.innerHTML += `<tr>
                    <td>${m.name}</td>
                    <td><code>${m.regex}</code></td>
                    <td>${m.type}</td>
                    <td><button onclick="deleteMetric(${m.id})" style="background:red; padding:5px;">Excluir</button></td>
                </tr>`;
            });

            // Atualiza Dropdown de Visualização
            if (metricSelect) {
                const currentVal = metricSelect.value;
                metricSelect.innerHTML = '<option value="">Selecione uma métrica para visualizar...</option>';
                metrics.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.id;
                    opt.textContent = m.name;
                    metricSelect.appendChild(opt);
                });
                if (currentVal) metricSelect.value = currentVal;
            }

        } catch (e) {
            tbody.innerHTML = '<tr><td colspan="4">Erro ao carregar.</td></tr>';
        } finally {
            stopGlobalLoading();
        }
    }

    async function loadMetricChart(id) {
        startGlobalLoading();
        const params = new URLSearchParams({
            search: currentFilters.search,
            level: currentFilters.level,
            source: currentFilters.source
        });

        try {
            const response = await fetch(`/api/metrics/${id}/data?${params}`);
            if (!response.ok) throw new Error('Falha ao buscar dados da métrica');
            const data = await response.json();
            const lineColors = getLineChartColors();
            const themeOptions = getChartThemeOptions();
            
            // Render Stats
            const statsDiv = document.getElementById('metric-stats');
            if (data.stats.count) {
                statsDiv.innerHTML = `
                    <span>Média: ${data.stats.mean}</span>
                    <span>Máx: ${data.stats.max}</span>
                    <span>Min: ${data.stats.min}</span>
                    <span>Amostras: ${data.stats.count}</span>
                `;
            } else {
                statsDiv.innerHTML = '<span>Sem dados para exibir com os filtros atuais.</span>';
            }

            // Render Chart
            const ctx = document.getElementById('metric-chart').getContext('2d');
            if (metricChart) metricChart.destroy();
            
            metricChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels.map(t => new Date(t).toLocaleTimeString()),
                    datasets: [{
                        label: 'Valor',
                        data: data.values,
                        borderColor: lineColors.accent.borderColor,
                        backgroundColor: lineColors.accent.backgroundColor,
                        fill: true,
                        tension: 0.1
                    }]
                },
                options: { ...themeOptions, responsive: true, maintainAspectRatio: false }
            });
        } catch (e) {
            console.error("Erro ao carregar gráfico da métrica", e);
        } finally {
            stopGlobalLoading();
        }
    }

    // Expor função globalmente para o botão onclick
    window.deleteMetric = async (id) => {
        if(!confirm("Tem certeza?")) return;
        await fetch(`/api/metrics/${id}`, { method: 'DELETE' });
        loadMetricsList();
    };

    // --- Lógica da Página RUM ---

    async function loadRumData() {
        startGlobalLoading();
        try {
            const response = await fetch('/api/analysis/rum');
            if (!response.ok) return; // Evita erro se não houver dados (404)
            const data = await response.json();
            
            const barColors = getBarChartColors();
            const themeOptions = getChartThemeOptions();

            // Render Vitals Chart
            const ctxVitals = document.getElementById('rum-vitals-chart').getContext('2d');
            if (rumVitalsChart) rumVitalsChart.destroy();
            
            rumVitalsChart = new Chart(ctxVitals, {
                type: 'bar',
                data: {
                    labels: data.vitals.map(v => v.name),
                    datasets: [{
                        label: 'Valor Médio',
                        data: data.vitals.map(v => v.value),
                        backgroundColor: barColors.success,
                        borderWidth: 1
                    }]
                },
                options: { ...themeOptions, responsive: true, maintainAspectRatio: false }
            });

            // Render Errors Chart
            const ctxErrors = document.getElementById('rum-errors-chart').getContext('2d');
            if (rumErrorsChart) rumErrorsChart.destroy();
            
            rumErrorsChart = new Chart(ctxErrors, {
                type: 'bar',
                data: {
                    labels: data.errors.map(e => e.name),
                    datasets: [{
                        label: 'Ocorrências',
                        data: data.errors.map(e => e.count),
                        backgroundColor: barColors.error,
                        borderWidth: 1
                    }]
                },
                options: { ...themeOptions, responsive: true, maintainAspectRatio: false, indexAxis: 'y' } // Barra horizontal
            });

            // Render Table
            const tbody = document.querySelector('#rum-errors-table tbody');
            tbody.innerHTML = '';
            if (data.error_details.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:#64748b;">Nenhum erro JS encontrado.</td></tr>';
            } else {
                // Ordena os erros do mais recente para o mais antigo
                data.error_details.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                data.error_details.forEach(err => {
                    tbody.innerHTML += `<tr>
                        <td>${err.timestamp}</td>
                        <td>${err.name}</td>
                        <td style="word-break: break-all;">${err.details}</td>
                    </tr>`;
                });
            }

        } catch (e) {
            console.error("Erro RUM", e);
        } finally {
            stopGlobalLoading();
        }
    }

    // --- Lógica da Página de Infraestrutura ---

    async function loadInfrastructureData() {
        startGlobalLoading();
        try {
            const response = await fetch('/api/analysis/infrastructure');
            const result = await response.json();
            const data = result.data;

            // Update KPIs
            const kpiNodes = document.getElementById('infra-kpi-nodes');
            const kpiStatus = document.getElementById('infra-kpi-status');
            const kpiJournal = document.getElementById('infra-kpi-journal');

            if (kpiNodes) kpiNodes.textContent = data.length;

            if (data.length > 0) {
                // Status: Se algum nó não for 'ALIVE', mostra 'DEGRADED'
                const isDegraded = data.some(d => d.lb_status !== 'ALIVE');
                if (kpiStatus) {
                    kpiStatus.textContent = isDegraded ? 'DEGRADED' : 'ALIVE';
                    kpiStatus.style.color = isDegraded ? '#f59e0b' : '#16a34a'; // amber / green
                }
                // Journal: Soma de todas as filas
                const totalJournal = data.reduce((sum, d) => sum + (d.journal_uncommitted || 0), 0);
                if (kpiJournal) kpiJournal.textContent = totalJournal.toLocaleString();
            } else {
                if (kpiStatus) { kpiStatus.textContent = 'N/A'; kpiStatus.style.color = ''; }
                if (kpiJournal) kpiJournal.textContent = 'N/A';
            }

            if (data.length === 0) {
                // Se não houver dados, limpa os gráficos existentes
                if (infraCpuChart) { infraCpuChart.destroy(); infraCpuChart = null; }
                if (infraMemChart) { infraMemChart.destroy(); infraMemChart = null; }
                if (infraDiskChart) { infraDiskChart.destroy(); infraDiskChart = null; }
                return;
            }

            const lineColors = getLineChartColors();
            // Prepara dados para os gráficos (Agrupando por Source)
            // 1. Extrai todos os timestamps únicos ordenados para o eixo X
            const allTimestamps = [...new Set(data.map(d => d.timestamp))].sort();
            const labels = allTimestamps.map(t => new Date(t).toLocaleTimeString());

            // 2. Identifica sources únicos
            const sources = [...new Set(data.map(d => d.source))];

            // Função auxiliar para criar datasets
            const createDatasets = (metricKey) => {
                return sources.map((source, index) => {
                    // Filtra dados deste source
                    const sourceData = data.filter(d => d.source === source);
                    
                    // Mapeia para o eixo X global (preenchendo gaps com null)
                    const dataPoints = allTimestamps.map(ts => {
                        const entry = sourceData.find(d => d.timestamp === ts);
                        return entry ? entry[metricKey] : null;
                    });

                    // Gera cor baseada no índice
                    const color = lineColors.dynamic(index);

                    return {
                        label: source,
                        data: dataPoints,
                        borderColor: color,
                        backgroundColor: color,
                        fill: false,
                        tension: 0.1,
                        spanGaps: true // Conecta linhas mesmo com gaps
                    };
                });
            };

            // Renderiza Gráficos
            infraCpuChart = renderLineChart('infra-cpu-chart', infraCpuChart, labels, createDatasets('cpu'));
            infraMemChart = renderLineChart('infra-mem-chart', infraMemChart, labels, createDatasets('memory'));
            infraDiskChart = renderLineChart('infra-disk-chart', infraDiskChart, labels, createDatasets('disk'));

        } catch (e) {
            console.error("Erro Infra", e);
        } finally {
            stopGlobalLoading();
        }
    }

    function renderLineChart(canvasId, chartInstance, labels, datasets) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        if (chartInstance) chartInstance.destroy();
        
        return new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: { ...getChartThemeOptions(), responsive: true, maintainAspectRatio: false }
        });
    }

    // --- Lógica da Página de Monitoramento de API ---

    async function loadApiData() {
        startGlobalLoading();
        const searchInput = document.getElementById('api-search-input');
        const sourceFilter = document.getElementById('api-source-filter');
        const streamFilter = document.getElementById('api-stream-filter');
        const applyBtn = document.getElementById('api-apply-filters-btn');

        const search = searchInput ? searchInput.value : '';
        const source = sourceFilter ? sourceFilter.value : '';
        const stream = streamFilter ? streamFilter.value : '';

        if (applyBtn) {
            applyBtn.disabled = true;
            applyBtn.textContent = 'Carregando...';
        }

        try {
            const params = new URLSearchParams();
            if (search) params.append('search', search);
            if (source && source !== 'Todos') params.append('source', source);
            if (stream && stream !== 'Todos') params.append('stream_id', stream);

            const response = await fetch(`/api/analysis/api-metrics?${params.toString()}`);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Falha ao carregar métricas de API');
            }
            const data = await response.json();
            
            const themeOptions = getChartThemeOptions();
            const barColors = getBarChartColors();

            // KPIs
            document.getElementById('api-kpi-total').textContent = data.stats.total;
            document.getElementById('api-kpi-success').textContent = data.stats.success;
            document.getElementById('api-kpi-client').textContent = data.stats.client_error;
            document.getElementById('api-kpi-server').textContent = data.stats.server_error;
            
            // Status Chart (Doughnut)
            const ctxStatus = document.getElementById('api-status-chart').getContext('2d');
            if (apiStatusChart) apiStatusChart.destroy();
            apiStatusChart = new Chart(ctxStatus, {
                type: 'doughnut',
                data: {
                    labels: data.status_counts.map(d => d.code),
                    datasets: [{
                        data: data.status_counts.map(d => d.count),
                        backgroundColor: getPieChartColors(),
                        borderColor: document.documentElement.classList.contains('dark') ? '#1e293b' : '#ffffff',
                        borderWidth: 2
                    }]
                },
                options: { ...getChartThemeOptions(), responsive: true, maintainAspectRatio: false }
            });
            
            // Method Chart (Doughnut)
            const ctxMethod = document.getElementById('api-method-chart').getContext('2d');
            if (apiMethodChart) apiMethodChart.destroy();
            apiMethodChart = new Chart(ctxMethod, {
                type: 'doughnut',
                data: {
                    labels: data.method_counts.map(d => d.method),
                    datasets: [{
                        data: data.method_counts.map(d => d.count),
                        backgroundColor: getPieChartColors(),
                        borderColor: document.documentElement.classList.contains('dark') ? '#1e293b' : '#ffffff',
                        borderWidth: 2
                    }]
                },
                options: { ...themeOptions, responsive: true, maintainAspectRatio: false }
            });
            
            // Endpoint Chart (Horizontal Bar)
            const ctxEndpoint = document.getElementById('api-endpoint-chart').getContext('2d');
            if (apiEndpointChart) apiEndpointChart.destroy();
            apiEndpointChart = new Chart(ctxEndpoint, {
                type: 'bar',
                data: {
                    labels: data.top_endpoints.map(d => d.endpoint),
                    datasets: [{
                        label: 'Acessos',
                        data: data.top_endpoints.map(d => d.count),
                        backgroundColor: barColors.secondary
                    }]
                },
                options: { 
                    ...themeOptions,
                    indexAxis: 'y',
                    responsive: true, 
                    maintainAspectRatio: false 
                }
            });

        } catch (e) {
            console.error("Erro API Metrics", e);
            showError(`Erro ao carregar métricas de API: ${e.message}`);
        } finally {
            if (applyBtn) {
                applyBtn.disabled = false;
                applyBtn.textContent = 'Aplicar Filtros';
            }
            stopGlobalLoading();
        }
    }

    // Adiciona listeners para a página de Monitoramento de API
    const apiApplyBtn = document.getElementById('api-apply-filters-btn');
    if (apiApplyBtn) {
        apiApplyBtn.addEventListener('click', loadApiData);
    }

    // Popula o filtro de source quando a página carrega
    const apiSourceFilter = document.getElementById('api-source-filter');
    if (apiSourceFilter) {
        fetch('/api/data/filters')
            .then(res => res.ok ? res.json() : Promise.reject('Failed to load filters'))
            .then(data => {
                data.sources.forEach(source => apiSourceFilter.add(new Option(source, source)));
            })
            .catch(err => console.error("Error populating API source filter:", err));
    }

    // Popula o filtro de stream na página de Monitoramento de API
    const apiStreamFilter = document.getElementById('api-stream-filter');
    if (apiStreamFilter) {
        fetch('/api/streams')
            .then(res => res.ok ? res.json() : Promise.reject('Failed to load streams'))
            .then(data => {
                apiStreamFilter.innerHTML = '<option value="Todos">Todos</option>';
                data.streams.forEach(stream => apiStreamFilter.add(new Option(stream.title, stream.id)));
            })
            .catch(err => console.error("Error populating API stream filter:", err));
    }

    // --- Lógica da Página de CI/CD ---

    async function loadCicdData() {
        startGlobalLoading();
        try {
            const response = await fetch('/api/analysis/cicd');
            const data = await response.json();
            
            const themeOptions = getChartThemeOptions();
            const barColors = getBarChartColors();

            // KPIs
            const kpiTotal = document.getElementById('cicd-kpi-total');
            if (kpiTotal) kpiTotal.textContent = data.stats.total;

            const kpiSuccessRate = document.getElementById('cicd-kpi-success-rate');
            if (kpiSuccessRate) kpiSuccessRate.textContent = `${data.stats.success_rate}%`;

            const kpiDuration = document.getElementById('cicd-kpi-duration');
            if (kpiDuration) kpiDuration.textContent = `${data.stats.avg_duration}s`;
            
            // Status Chart (Pie)
            const ctxStatus = document.getElementById('cicd-status-chart').getContext('2d');
            if (cicdStatusChart) cicdStatusChart.destroy();
            cicdStatusChart = new Chart(ctxStatus, {
                type: 'pie',
                data: {
                    labels: data.status_counts.map(d => d.status),
                    datasets: [{
                        data: data.status_counts.map(d => d.count),
                        backgroundColor: getPieChartColors(),
                        borderColor: document.documentElement.classList.contains('dark') ? '#1e293b' : '#ffffff',
                        borderWidth: 2
                    }]
                },
                options: { ...getChartThemeOptions(), responsive: true, maintainAspectRatio: false }
            });
            
            // Duration Chart (Bar)
            const ctxDuration = document.getElementById('cicd-duration-chart').getContext('2d');
            if (cicdDurationChart) cicdDurationChart.destroy();
            cicdDurationChart = new Chart(ctxDuration, {
                type: 'bar',
                data: {
                    labels: data.stage_duration.map(d => d.stage),
                    datasets: [{
                        label: 'Duração Média (s)',
                        data: data.stage_duration.map(d => d.avg_duration),
                        backgroundColor: barColors.primary
                    }]
                },
                options: { ...themeOptions, responsive: true, maintainAspectRatio: false }
            });
            
            // Table
            const tbody = document.querySelector('#cicd-table tbody');
            tbody.innerHTML = '';
            if (data.recent_builds.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Nenhum dado de CI/CD encontrado.</td></tr>';
            } else {
                // Ordena os builds do mais recente para o mais antigo
                data.recent_builds.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                data.recent_builds.forEach(item => {
                    const tr = document.createElement('tr');
                    tr.className = 'cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors';
                    tr.innerHTML = `
                        <td>${item.timestamp}</td>
                        <td>${item.stage}</td>
                        <td>${item.status}</td>
                        <td>${item.duration_s}s</td>
                        <td style="word-break: break-all;">${item.message.substring(0, 50)}...</td>
                    `;
                    tr.addEventListener('click', () => {
                        openLogModal({
                            timestamp: item.timestamp,
                            log_level: item.status,
                            source: item.source || item.stage,
                            category: 'CI/CD Pipeline',
                            message: item.message
                        });
                    });
                    tbody.appendChild(tr);
                });
            }
        } catch (e) {
            console.error("Erro CI/CD", e);
        } finally {
            stopGlobalLoading();
        }
    }

    // --- Lógica da Página de Streams ---

    async function loadStreamsData() {
        startGlobalLoading();
        const tbody = document.querySelector('#streams-table tbody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">Carregando streams...</td></tr>';

        try {
            const response = await fetch('/api/streams');
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Falha ao buscar streams');
            }
            const data = await response.json();

            tbody.innerHTML = '';
            if (data.streams.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center">Nenhuma stream ativa encontrada.</td></tr>';
                return;
            }

            data.streams.forEach(stream => {
                const isPaused = stream.paused;
                const statusText = isPaused ? 'Pausada' : 'Rodando';
                const statusClass = isPaused ? 'bg-yellow-200 text-yellow-800 dark:bg-yellow-800/30 dark:text-yellow-300' : 'bg-green-200 text-green-800 dark:bg-green-800/30 dark:text-green-300';
                const throughput = stream.throughput ? stream.throughput.toFixed(2) : '0.00';

                const tr = document.createElement('tr');
                tr.className = 'cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50';
                tr.dataset.streamId = stream.id;
                tr.dataset.action = 'toggle-stream-details';

                tr.innerHTML = `
                    <td class="px-6 py-4"><i data-lucide="chevron-right" class="w-4 h-4 text-slate-400 transition-transform"></i></td>
                    <td class="px-6 py-4">${stream.title}</td>
                    <td class="px-6 py-4">${stream.description || 'N/A'}</td>
                    <td class="px-6 py-4"><span class="px-2 py-1 text-xs font-medium rounded-full ${statusClass}">${statusText}</span></td>
                    <td class="px-6 py-4">${throughput} msg/s</td>
                `;
                tbody.appendChild(tr);

                const detailsTr = document.createElement('tr');
                detailsTr.id = `details-${stream.id}`;
                detailsTr.classList.add('hidden');
                detailsTr.innerHTML = `<td colspan="5" class="p-4 bg-slate-100 dark:bg-slate-900/50"></td>`;
                tbody.appendChild(detailsTr);
            });
            lucide.createIcons();
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center text-red-500">Erro: ${e.message}</td></tr>`;
        } finally {
            stopGlobalLoading();
        }
    }

    const streamsTableBody = document.querySelector('#streams-table tbody');
    if (streamsTableBody) {
        streamsTableBody.addEventListener('click', async (e) => {
            const row = e.target.closest('tr[data-action="toggle-stream-details"]');
            if (!row) return;

            const streamId = row.dataset.streamId;
            const detailsRow = document.getElementById(`details-${streamId}`);
            const icon = row.querySelector('i[data-lucide]');

            const isVisible = !detailsRow.classList.contains('hidden');
            if (isVisible) {
                detailsRow.classList.add('hidden');
                if (icon) icon.classList.remove('rotate-90');
                return;
            }

            detailsRow.classList.remove('hidden');
            if (icon) icon.classList.add('rotate-90');
            const detailsCell = detailsRow.querySelector('td');
            detailsCell.innerHTML = '<p class="text-slate-500">Carregando detalhes...</p>';

            try {
                const response = await fetch(`/api/streams/${streamId}/details`);
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Falha ao buscar detalhes da stream');
                }
                const data = await response.json();

                let rulesHtml = '<p class="text-sm text-slate-500">Nenhuma regra de roteamento configurada.</p>';
                if (data.rules && data.rules.length > 0) {
                    rulesHtml = data.rules.map(rule => `
                        <li class="flex items-start gap-2 p-2 border-b border-slate-200 dark:border-slate-700 last:border-b-0">
                            <i data-lucide="filter" class="w-4 h-4 text-blue-500 mt-1 flex-shrink-0"></i>
                            <div>
                                <p class="font-mono text-xs"><strong class="font-semibold">Campo:</strong> ${rule.field}</p>
                                <p class="font-mono text-xs"><strong class="font-semibold">Valor:</strong> ${rule.value} <em class="text-slate-400">(${rule.type})</em></p>
                                ${rule.inverted ? '<p class="text-xs text-amber-500">(Regra Invertida)</p>' : ''}
                            </div>
                        </li>`).join('');
                    rulesHtml = `<ul class="space-y-1">${rulesHtml}</ul>`;
                }

                detailsCell.innerHTML = `<div class="space-y-2"><h5 class="text-md font-semibold text-slate-700 dark:text-slate-200">Regras de Roteamento</h5>${rulesHtml}</div>`;
                lucide.createIcons();
            } catch (error) {
                detailsCell.innerHTML = `<p class="text-red-500">Erro: ${error.message}</p>`;
            }
        });
    }

    // --- Lógica da Página de Alertas ---

    async function toggleAlert(id, enable) {
        if (!confirm(`Tem certeza que deseja ${enable ? 'ativar' : 'desativar'} este alerta?`)) return;
        try {
            const response = await fetch(`/api/alerts/definitions/${id}/schedule`, { method: enable ? 'PUT' : 'DELETE' });
            if (!response.ok) { const error = await response.json(); throw new Error(error.detail || 'Falha ao alterar o estado do alerta.'); }
            showSuccess(`Alerta ${enable ? 'ativado' : 'desativado'} com sucesso!`);
            loadAlertDefinitions();
        } catch (e) { showError(`Erro: ${e.message}`); }
    }

    async function testAlert(id) {
        if (!confirm('Isso executará a verificação do alerta agora. Deseja continuar?')) return;
        showLoading('Executando verificação do alerta...');
        try {
            const response = await fetch(`/api/alerts/definitions/${id}/execute`, { method: 'POST' });
            if (!response.ok) { const error = await response.json(); throw new Error(error.detail || 'Falha ao executar o teste.'); }
            const result = await response.json();
            showSuccess(`Verificação concluída. O alerta ${result.triggered ? 'FOI DISPARADO' : 'NÃO foi disparado'}.`);
            loadTriggeredAlerts();
        } catch (e) { showError(`Erro no teste: ${e.message}`); }
    }

    async function loadAlertsData() {
        startGlobalLoading();
        try {
            await Promise.all([
                loadAlertDefinitions(),
                loadTriggeredAlerts()
            ]);
        } finally {
            stopGlobalLoading();
        }
    }

    async function loadAlertDefinitions() {
        startGlobalLoading();
        const tbody = document.querySelector('#alert-definitions-table tbody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">Carregando definições de alerta...</td></tr>';

        try {
            const response = await fetch('/api/alerts/definitions');
            if (!response.ok) {
                let errorMsg = `Erro HTTP ${response.status}: ${response.statusText}`;
                try {
                    const errorJson = await response.json();
                    errorMsg = errorJson.detail || errorMsg;
                } catch (jsonError) { /* A resposta pode não ser JSON, ignore o erro de parsing */ }
                throw new Error(errorMsg);
            }
            const data = await response.json();

            tbody.innerHTML = '';
            if (data.event_definitions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center">Nenhuma definição de alerta encontrada.</td></tr>';
                return;
            }

            data.event_definitions.forEach(def => {
                const isScheduled = def.config.scheduler_type !== 'none';
                const scheduleType = isScheduled ? `(${def.config.scheduler_type})` : '(Desativado)';
                const toggleButtonText = isScheduled ? 'Desativar' : 'Ativar';
                const toggleButtonClass = isScheduled ? 'bg-yellow-500 hover:bg-yellow-600' : 'bg-green-500 hover:bg-green-600';

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${def.title}</td>
                    <td>${def.description || 'N/A'}</td>
                    <td>${def.priority}</td>
                    <td>${scheduleType}</td>
                    <td class="space-x-2">
                        <button data-action="toggle-alert" data-id="${def.id}" data-enable="${!isScheduled}" class="px-2 py-1 text-xs text-white rounded ${toggleButtonClass}">${toggleButtonText}</button>
                        <button data-action="test-alert" data-id="${def.id}" class="px-2 py-1 text-xs text-white rounded bg-blue-500 hover:bg-blue-600">Testar</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center text-red-500">Erro: ${e.message}</td></tr>`;
        } finally {
            stopGlobalLoading();
        }
    }

    async function loadTriggeredAlerts() {
        startGlobalLoading();
        const tbody = document.querySelector('#triggered-alerts-table tbody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="4" class="text-center">Carregando alertas disparados...</td></tr>';

        try {
            const response = await fetch('/api/alerts/triggered');
            if (!response.ok) {
                let errorMsg = `Erro HTTP ${response.status}: ${response.statusText}`;
                try {
                    const errorJson = await response.json();
                    errorMsg = errorJson.detail || errorMsg;
                } catch (jsonError) { /* A resposta pode não ser JSON, ignore o erro de parsing */ }
                throw new Error(errorMsg);
            }
            const data = await response.json();

            tbody.innerHTML = '';
            if (data.alerts.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-center text-slate-500 dark:text-slate-400">Nenhum alerta disparado recentemente.</td></tr>';
                return;
            }

            data.alerts.forEach(alert => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${new Date(alert.triggered_at).toLocaleString()}</td>
                    <td>${alert.stream_title || 'N/A'}</td>
                    <td>${alert.condition_title || 'N/A'}</td>
                    <td class="whitespace-pre-wrap">${alert.description}</td>
                `;
                tbody.appendChild(tr);
            });

        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center text-red-500">Erro: ${e.message}</td></tr>`;
        } finally {
            stopGlobalLoading();
        }
    }

    // Adiciona um listener de eventos na tabela de definições para delegar os cliques nos botões
    const alertDefinitionsTable = document.querySelector('#alert-definitions-table');
    if (alertDefinitionsTable) {
        alertDefinitionsTable.addEventListener('click', (e) => {
            const button = e.target.closest('button[data-action]');
            if (!button) return;

            const action = button.dataset.action;
            const id = button.dataset.id;

            if (action === 'toggle-alert') {
                const enable = button.dataset.enable === 'true';
                toggleAlert(id, enable);
            } else if (action === 'test-alert') {
                testAlert(id);
            }
        });
    }

    // --- Lógica da Página de Ferramentas Técnicas ---

    // 1. RCA
    const btnRunLoadTest = document.getElementById('btn-run-load-test');
    if (btnRunLoadTest) {
        btnRunLoadTest.addEventListener('click', async () => {
            const resultsContainer = document.getElementById('load-test-results-container');
            const url = document.getElementById('load-test-url').value;
            const requests = parseInt(document.getElementById('load-test-requests').value, 10);
            const concurrency = parseInt(document.getElementById('load-test-concurrency').value, 10);

            if (!url) {
                resultsContainer.innerHTML = `<p class="text-red-500">Por favor, insira uma URL.</p>`;
                return;
            }

            btnRunLoadTest.disabled = true;
            btnRunLoadTest.textContent = 'Executando...';
            resultsContainer.innerHTML = `<p class="text-slate-500 dark:text-slate-400">Iniciando teste de carga... Isso pode levar um tempo.</p>`;

            try {
                const response = await fetch('/api/tools/load-test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, requests, concurrency, method: 'GET' })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `Erro HTTP ${response.status}`);
                }

                const data = await response.json();
                
                let statusDistHtml = '';
                for (const [status, count] of Object.entries(data.status_code_distribution)) {
                    const isError = !(parseInt(status) >= 200 && parseInt(status) < 400);
                    statusDistHtml += `<span class="mr-2 mb-1 inline-block px-2 py-1 text-xs rounded ${isError ? 'bg-red-200 text-red-800' : 'bg-green-200 text-green-800'}">${status}: ${count}x</span>`;
                }

                resultsContainer.innerHTML = `
                    <h5 class="text-md font-semibold mb-2 text-slate-800 dark:text-slate-100">Resultados do Teste</h5>
                    <div class="grid grid-cols-2 gap-2 text-sm">
                        <div><p class="text-slate-500">Duração Total:</p><p class="font-bold text-slate-700 dark:text-slate-200">${data.total_duration_seconds} s</p></div>
                        <div><p class="text-slate-500">Reqs/segundo:</p><p class="font-bold text-slate-700 dark:text-slate-200">${data.requests_per_second}</p></div>
                        <div><p class="text-slate-500">Latência Média:</p><p class="font-bold text-slate-700 dark:text-slate-200">${data.average_latency_ms} ms</p></div>
                        <div><p class="text-slate-500">Sucesso / Erro:</p><p class="font-bold"><span class="text-green-600">${data.success_count}</span> / <span class="text-red-600">${data.error_count}</span></p></div>
                    </div>
                    <div class="mt-4"><p class="text-slate-500 text-sm mb-2">Distribuição de Status:</p><div>${statusDistHtml}</div></div>`;

            } catch (error) {
                resultsContainer.innerHTML = `<p class="text-red-500">Falha no teste: ${error.message}</p>`;
            } finally {
                btnRunLoadTest.disabled = false;
                btnRunLoadTest.textContent = 'Iniciar Teste de Carga';
            }
        });
    }
    const btnRunRca = document.getElementById('btn-run-rca');
    if (btnRunRca) {
        btnRunRca.addEventListener('click', async () => {
        const container = document.getElementById('rca-result-container');
        const content = document.getElementById('rca-content');
        
        container.style.display = 'block';
        content.innerHTML = 'Gerando diagnóstico... (Isso pode levar alguns segundos)';
        
        const formData = new FormData();
        // Passa os filtros atuais para a RCA analisar o contexto correto
        formData.append('search', currentFilters.search);
        formData.append('level', currentFilters.level);
        formData.append('source', currentFilters.source);
        
        try {
            const response = await fetch('/api/analysis/rca', { method: 'POST', body: formData });
            const data = await response.json();
            
            // Formatação simples de Markdown para HTML
            let formatted = data.result
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold
                .replace(/\n/g, '<br>'); // Newlines
                
            content.innerHTML = formatted;
        } catch (e) {
            content.innerHTML = `<span style="color:red">Erro: ${e.message}</span>`;
        }
    });
    }

    // 2. Regex Sandbox (Reutiliza endpoint de métricas)
    const btnToolsTestRegex = document.getElementById('tools-test-regex-btn');
    if (btnToolsTestRegex) {
        btnToolsTestRegex.addEventListener('click', async () => {
        const regex = document.getElementById('tools-regex-input').value;
        const resultsDiv = document.getElementById('tools-regex-results');
        
        if (!regex) return;
        resultsDiv.innerHTML = 'Testando...';
        
        const formData = new FormData();
        formData.append('regex', regex);
        
        try {
            const response = await fetch('/api/metrics/test', { method: 'POST', body: formData });
            const data = await response.json();
            
            if (!response.ok) throw new Error(data.detail);
            resultsDiv.innerHTML = `<p><strong>${data.count}</strong> matches encontrados.</p>`;
        } catch (e) {
            resultsDiv.innerHTML = `<p style="color:red">Erro: ${e.message}</p>`;
        }
    });
    }

    // Simulador de Requisições HTTP (Mini-Postman)
    const btnHttpSend = document.getElementById('btn-http-client-send');
    if (btnHttpSend) {
        btnHttpSend.addEventListener('click', async () => {
            const url = document.getElementById('http-client-url').value.trim();
            const method = document.getElementById('http-client-method').value;
            const headersText = document.getElementById('http-client-headers').value.trim();
            const bodyText = document.getElementById('http-client-body').value.trim();
            
            const responseContainer = document.getElementById('http-client-response');
            const statusBadge = document.getElementById('http-client-status');

            if (!url) {
                responseContainer.textContent = "Por favor, insira uma URL válida.";
                statusBadge.classList.add('hidden');
                return;
            }

            btnHttpSend.disabled = true;
            btnHttpSend.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Enviando...';
            lucide.createIcons();

            let headers = {};
            try {
                if (headersText) headers = JSON.parse(headersText);
            } catch (e) {
                responseContainer.textContent = "Erro nos Headers. Verifique se estão no formato JSON válido.\nExemplo: { \"Content-Type\": \"application/json\" }";
                btnHttpSend.disabled = false;
                btnHttpSend.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i> Enviar Requisição';
                lucide.createIcons();
                return;
            }

            const fetchOptions = { method, headers };

            if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) && bodyText) {
                fetchOptions.body = bodyText;
                // Tenta inferir se é JSON para colocar o Header de Content-Type automaticamente (Postman faz isso)
                if (!headers['Content-Type']) {
                    try { JSON.parse(bodyText); fetchOptions.headers['Content-Type'] = 'application/json'; } catch (e) {}
                }
            }

            try {
                const startTime = performance.now();
                const response = await fetch(url, fetchOptions);
                const duration = Math.round(performance.now() - startTime);

                statusBadge.classList.remove('hidden', 'bg-slate-200', 'text-slate-600', 'bg-green-200', 'text-green-800', 'bg-red-200', 'text-red-800');
                statusBadge.classList.add(response.ok ? 'bg-green-200' : 'bg-red-200', response.ok ? 'text-green-800' : 'text-red-800');
                statusBadge.textContent = `${response.status} ${response.statusText} - ${duration}ms`;

                const contentType = response.headers.get("content-type");
                const responseData = (contentType && contentType.includes("application/json")) 
                    ? JSON.stringify(await response.json(), null, 2) 
                    : await response.text();

                responseContainer.textContent = responseData || "(A resposta veio vazia)";
            } catch (error) {
                statusBadge.classList.remove('hidden', 'bg-slate-200', 'text-slate-600', 'bg-green-200', 'text-green-800');
                statusBadge.classList.add('bg-red-200', 'text-red-800');
                statusBadge.textContent = "Erro de Rede / CORS";
                responseContainer.textContent = `Falha ao realizar a requisição:\n${error.message}\n\nDica: Se testou uma API externa (fora da Lockton), ela pode estar bloqueando o navegador via CORS. Para APIs locais como o Webhook Catcher, funcionará perfeitamente.`;
            } finally {
                btnHttpSend.disabled = false;
                btnHttpSend.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i> Enviar Requisição';
                lucide.createIcons();
            }
        });
    }

    // 3. Webhook Catcher
    const webhookUrlDisplay = document.getElementById('webhook-url-display');
    const webhookCopyBtn = document.getElementById('webhook-copy-btn');
    const webhookRefreshBtn = document.getElementById('webhook-refresh-btn');
    const webhookClearBtn = document.getElementById('webhook-clear-btn');
    const webhookRequestList = document.getElementById('webhook-request-list');
    const webhookRequestDetails = document.getElementById('webhook-request-details');
    const webhookCount = document.getElementById('webhook-count');
    
    let cachedWebhookLogs = [];
    let selectedWebhookId = null;

    if (webhookUrlDisplay) {
            // Define a URL padrão solicitada
            webhookUrlDisplay.value = "http://10.130.0.20:8051/api/tools/webhook-catcher/test";

        webhookCopyBtn.addEventListener('click', () => {
                // Copia o valor atualizado que o usuário pode ter editado
                navigator.clipboard.writeText(webhookUrlDisplay.value);
            const originalText = webhookCopyBtn.innerHTML;
            webhookCopyBtn.innerHTML = '<i data-lucide="check" class="w-4 h-4"></i> Copiado!';
            lucide.createIcons();
            setTimeout(() => {
                webhookCopyBtn.innerHTML = originalText;
                lucide.createIcons();
            }, 2000);
        });

        const getMethodColor = (method) => {
            const colors = { 'GET': 'text-blue-600 bg-blue-100', 'POST': 'text-green-600 bg-green-100', 'PUT': 'text-amber-600 bg-amber-100', 'DELETE': 'text-red-600 bg-red-100' };
            return colors[method] || 'text-slate-600 bg-slate-100';
        };

        const renderWebhookDetails = (log) => {
            if (!log) {
                webhookRequestDetails.innerHTML = `<div class="h-full flex items-center justify-center text-slate-400 text-sm">Selecione uma requisição ao lado para ver os detalhes.</div>`;
                return;
            }
            let bodyContent = log.body;
            if (typeof log.body === 'object' && log.body !== null) bodyContent = JSON.stringify(log.body, null, 2);
            else if (log.body === null) bodyContent = '(Nenhum corpo na requisição)';

            webhookRequestDetails.innerHTML = `
                <div class="space-y-4">
                    <div class="flex items-center gap-2 border-b border-slate-200 dark:border-slate-700 pb-2">
                        <span class="px-2 py-0.5 text-xs font-bold rounded ${getMethodColor(log.method)}">${log.method}</span>
                        <span class="font-mono text-sm text-slate-800 dark:text-slate-200">${log.path}</span>
                    </div>
                    <div>
                        <h6 class="text-xs font-bold text-slate-500 uppercase mb-1">Informações</h6>
                        <div class="text-sm font-mono text-slate-700 dark:text-slate-300">
                            <div>IP Cliente: <span class="text-blue-500">${log.client}</span></div>
                            <div>Data/Hora: ${log.timestamp}</div>
                        </div>
                    </div>
                    <div>
                        <h6 class="text-xs font-bold text-slate-500 uppercase mb-1">Query Params</h6>
                        <pre class="bg-white dark:bg-slate-800 p-2 rounded border border-slate-200 dark:border-slate-700 text-xs font-mono text-slate-700 dark:text-slate-300 overflow-x-auto">${Object.keys(log.query_params).length ? JSON.stringify(log.query_params, null, 2) : '(Vazio)'}</pre>
                    </div>
                    <div>
                        <h6 class="text-xs font-bold text-slate-500 uppercase mb-1">Headers</h6>
                        <pre class="bg-white dark:bg-slate-800 p-2 rounded border border-slate-200 dark:border-slate-700 text-xs font-mono text-slate-700 dark:text-slate-300 overflow-x-auto">${JSON.stringify(log.headers, null, 2)}</pre>
                    </div>
                    <div>
                        <h6 class="text-xs font-bold text-slate-500 uppercase mb-1">Body (Payload)</h6>
                        <pre class="bg-white dark:bg-slate-800 p-2 rounded border border-slate-200 dark:border-slate-700 text-xs font-mono text-slate-700 dark:text-slate-300 overflow-x-auto whitespace-pre-wrap">${bodyContent}</pre>
                    </div>
                </div>`;
        };

        const fetchWebhookLogs = async () => {
            try {
                const response = await fetch('/api/tools/webhook-catcher-logs');
                const data = await response.json();
                
                if (JSON.stringify(data.logs.map(l => l.id)) !== JSON.stringify(cachedWebhookLogs.map(l => l.id))) {
                    cachedWebhookLogs = data.logs;
                    webhookCount.textContent = cachedWebhookLogs.length;

                    if (cachedWebhookLogs.length === 0) {
                        webhookRequestList.innerHTML = `<div class="p-4 text-center text-slate-400 text-sm">Nenhuma requisição recebida.</div>`;
                        renderWebhookDetails(null);
                    } else {
                        webhookRequestList.innerHTML = cachedWebhookLogs.map(log => `
                            <div class="webhook-list-item p-3 border-b border-slate-100 dark:border-slate-700 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors ${log.id === selectedWebhookId ? 'bg-blue-50 dark:bg-slate-700' : ''}" data-id="${log.id}">
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="px-1.5 py-0.5 text-[10px] font-bold rounded ${getMethodColor(log.method)}">${log.method}</span>
                                    <span class="text-xs font-mono text-slate-600 dark:text-slate-400 truncate">${log.path}</span>
                                </div>
                                <div class="text-[10px] text-slate-400 text-right">${log.timestamp.split(' ')[1]}</div>
                            </div>`).join('');

                        document.querySelectorAll('.webhook-list-item').forEach(item => {
                            item.addEventListener('click', (e) => {
                                document.querySelectorAll('.webhook-list-item').forEach(el => el.classList.remove('bg-blue-50', 'dark:bg-slate-700'));
                                e.currentTarget.classList.add('bg-blue-50', 'dark:bg-slate-700');
                                selectedWebhookId = parseInt(e.currentTarget.getAttribute('data-id'));
                                renderWebhookDetails(cachedWebhookLogs.find(l => l.id === selectedWebhookId));
                            });
                        });
                        
                        if (!selectedWebhookId && cachedWebhookLogs.length > 0) {
                            document.querySelector('.webhook-list-item').click();
                        }
                    }
                }
            } catch (error) {}
        };

        webhookRefreshBtn.addEventListener('click', () => { fetchWebhookLogs(); });
        webhookClearBtn.addEventListener('click', async () => {
            if (confirm("Deseja realmente limpar todas as requisições capturadas?")) {
                await fetch('/api/tools/webhook-catcher-logs', { method: 'DELETE' });
                selectedWebhookId = null; 
                fetchWebhookLogs();
            }
        });

        // Auto-update (polling) a cada 3 segundos somente se a página de ferramentas estiver ativa
        setInterval(() => {
            const page = document.getElementById('tools-page');
            if (page && page.style.display !== 'none') fetchWebhookLogs();
        }, 3000);
    }

    // 4. Advanced Load Test
    const advForm = document.getElementById('advanced-load-test-form');
    if (advForm) {
        const placeholder = document.getElementById('advanced-load-test-placeholder');
        const loading = document.getElementById('advanced-load-test-loading');
        const resultsDiv = document.getElementById('advanced-load-test-results');
        const errorDiv = document.getElementById('advanced-load-test-error');
        const errorMessageSpan = document.getElementById('advanced-load-test-error-message');
        const submitBtn = advForm.querySelector('button[type="submit"]');

        advForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            // 1. Resetar UI
            placeholder.classList.add('hidden');
            resultsDiv.innerHTML = ''; // Limpa resultados antigos
            resultsDiv.classList.add('hidden');
            errorDiv.classList.add('hidden');
            loading.classList.remove('hidden');
            lucide.createIcons({ nodes: [loading.querySelector('i')] }); // Renderiza o ícone de spinner
            submitBtn.disabled = true;
            submitBtn.textContent = 'Executando...';

            // 2. Coletar dados do formulário
            const url = document.getElementById('adv-test-url').value;
            const duration_seconds = parseInt(document.getElementById('adv-test-duration').value, 10) || 30;
            const concurrency = parseInt(document.getElementById('adv-test-concurrency').value, 10) || 10;
            const ramp_up_seconds = parseInt(document.getElementById('adv-test-ramp-up').value, 10) || 0;
            const method = document.getElementById('adv-test-method').value;
            const headersText = document.getElementById('adv-test-headers').value;
            const bodyText = document.getElementById('adv-test-body').value;

            let headers = null;
            let body = null;

            try {
                if (headersText.trim()) headers = JSON.parse(headersText);
                if (bodyText.trim()) body = JSON.parse(bodyText);
            } catch (e) {
                errorMessageSpan.textContent = 'Erro ao processar Headers ou Body. Verifique se o JSON é válido.';
                errorDiv.classList.remove('hidden');
                loading.classList.add('hidden');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Iniciar Teste Avançado';
                return;
            }

            // 3. Montar payload e chamar API
            const payload = { url, duration_seconds, concurrency, ramp_up_seconds, method, headers, body };

            try {
                const response = await fetch('/api/tools/advanced-load-test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || 'Ocorreu um erro desconhecido.');
                }

                // 4. Popular os resultados na UI
                let statusDistHtml = '';
                for (const [code, count] of Object.entries(data.status_code_distribution)) {
                    const isError = !(parseInt(code) >= 200 && parseInt(code) < 400);
                    statusDistHtml += `<span class="mr-2 mb-1 inline-block px-2 py-1 text-xs rounded ${isError ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}">${code}: ${count}x</span>`;
                }

                resultsDiv.innerHTML = `
                    <h5 class="text-md font-semibold mb-2 text-slate-800 dark:text-slate-100">Resultados do Teste</h5>
                    <div class="grid grid-cols-2 gap-4 text-sm mb-4">
                        <div><p class="text-slate-500">Reqs/segundo:</p><p class="font-bold text-slate-700 dark:text-slate-200">${data.requests_per_second}</p></div>
                        <div><p class="text-slate-500">Total de Reqs:</p><p class="font-bold text-slate-700 dark:text-slate-200">${data.total_requests}</p></div>
                        <div><p class="text-slate-500">Sucesso / Erro:</p><p class="font-bold"><span class="text-green-600">${data.success_count}</span> / <span class="text-red-600">${data.error_count}</span></p></div>
                    </div>
                    <h5 class="text-md font-semibold mt-4 mb-2 text-slate-800 dark:text-slate-100">Latência (ms)</h5>
                    <div class="grid grid-cols-2 gap-4 text-sm">
                        <div><p class="text-slate-500">Média:</p><p class="font-bold text-slate-700 dark:text-slate-200">${data.average_latency_ms}</p></div>
                        <div><p class="text-slate-500">P50 (Mediana):</p><p class="font-bold text-slate-700 dark:text-slate-200">${data.p50_latency_ms}</p></div>
                        <div><p class="text-slate-500">P95:</p><p class="font-bold text-slate-700 dark:text-slate-200">${data.p95_latency_ms}</p></div>
                        <div><p class="text-slate-500">P99:</p><p class="font-bold text-slate-700 dark:text-slate-200">${data.p99_latency_ms}</p></div>
                    </div>
                    <div class="mt-4">
                        <p class="text-slate-500 text-sm mb-2">Distribuição de Status:</p>
                        <div>${statusDistHtml}</div>
                    </div>
                `;

                resultsDiv.classList.remove('hidden');

            } catch (error) {
                errorMessageSpan.textContent = error.message;
                errorDiv.classList.remove('hidden');
            } finally {
                loading.classList.add('hidden');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Iniciar Teste Avançado';
            }
        });
    }

    const btnClearAdvTest = document.getElementById('btn-clear-adv-test');
    if (btnClearAdvTest) {
        btnClearAdvTest.addEventListener('click', () => {
            const resultsContainer = document.getElementById('advanced-load-test-results');
            if (resultsContainer) {
                resultsContainer.classList.add('hidden');
                resultsContainer.innerHTML = '';
            }
            
            const errorContainer = document.getElementById('advanced-load-test-error');
            if (errorContainer) {
                errorContainer.classList.add('hidden');
            }
            
            const placeholder = document.getElementById('advanced-load-test-placeholder');
            if (placeholder) {
                placeholder.classList.remove('hidden');
            }
        });
    }

    // 5. Log Parser Tester
    const btnRunParseTest = document.getElementById('btn-run-parse-test');
    if (btnRunParseTest) {
        btnRunParseTest.addEventListener('click', async () => {
            const input = document.getElementById('log-parse-input');
            const resultsPre = document.getElementById('log-parse-results');
            const rawMessage = input.value.trim();

            if (!rawMessage) {
                resultsPre.textContent = 'Por favor, insira uma mensagem de log.';
                resultsPre.style.color = 'orange';
                return;
            }

            btnRunParseTest.disabled = true;
            btnRunParseTest.textContent = 'Analisando...';
            resultsPre.textContent = 'Aguardando resposta do Graylog...';
            resultsPre.style.color = '';

            try {
                const response = await fetch('/api/tools/parse-log', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ raw_message: rawMessage })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || `Erro HTTP ${response.status}`);
                }
                
                resultsPre.textContent = JSON.stringify(data, null, 2);
            } catch (error) {
                resultsPre.textContent = `Erro: ${error.message}`;
                resultsPre.style.color = 'red';
            } finally {
                btnRunParseTest.disabled = false;
                btnRunParseTest.textContent = 'Testar Parsing';
            }
        });
    }

    function showLoading(message) {
        loadingStatus.textContent = message;
        loadingStatus.style.color = '#333';
    }

    function showSuccess(message) {
        loadingStatus.textContent = message;
        loadingStatus.style.color = 'green';
    }

    function showError(message) {
        loadingStatus.textContent = message;
        loadingStatus.style.color = 'red';
    }
});