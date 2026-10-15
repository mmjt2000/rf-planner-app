// navigation.js - Système de navigation unifié
const NAV_ITEMS = [
    { href: '/', label: 'Link Budget', icon: '📡' },
    { href: '/pci_planner.html', label: 'PCI / PRACH', icon: '🔢' },
    { href: '/neighbor.html', label: 'Voisinage', icon: '🔗' },
    { href: '/nominal-planner.html', label: 'Nominal', icon: '📋' },
    { href: '/scenario-simulator.html', label: 'Simulateur', icon: '' },
    { href: '/terrain-import.html', label: 'Terrain', icon: '🗺️' }
];

function getCurrentPage() {
    const path = window.location.pathname;
    if (path === '/' || path === '/index.html') return '/';
    return path;
}

function renderNavigation() {
    const navContainer = document.getElementById('main-nav');
    if (!navContainer) return;
    
    const currentPage = getCurrentPage();
    
    navContainer.innerHTML = NAV_ITEMS.map(item => {
        const isActive = item.href === currentPage;
        return <a href="" class="nav-item ">
            <span class="nav-icon"></span>
            <span class="nav-label"></span>
        </a>;
    }).join('');
}

// Initialiser au chargement
document.addEventListener('DOMContentLoaded', renderNavigation);
