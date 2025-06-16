// Конфигурация
const CONFIG = {
    TON_PRICE: 0.1,
    RUB_PRICE: 10,
    BACKEND_URL: 'https://ваш-сервер.com/api',
    MANIFEST_URL: 'https://ваш-сайт.com/tonconnect-manifest.json',
    YOOMONEY_ID: 'ВАШ_MERCHANT_ID',
    IMAGE_PATHS: {
        TON: 'buy.png',
        RUB: 'rub.png'
    }
};

// Элементы DOM
let elements = {};
let connector;
let wallet;

// Инициализация приложения
async function initApp() {
    // Сбор элементов DOM
    collectDOMElements();

    // Инициализация TON Connect
    await initTonConnect();

    // Настройка обработчиков событий
    setupEventListeners();

    // Инициализация ЮMoney
    initYooMoney();

    // Инициализация цен
    updatePrices();

    // Установка изображений для виджетов
    setWidgetImages();

    // Загрузка реферальных данных если активна вкладка Партнерство
    if (elements.partnershipTab.classList.contains('active')) {
        loadRefData();
    }
}

// Установка изображений для виджетов
function setWidgetImages() {
    if (elements.tonImage) {
        elements.tonImage.src = CONFIG.IMAGE_PATHS.TON;
    }
    if (elements.rubImage) {
        elements.rubImage.src = CONFIG.IMAGE_PATHS.RUB;
    }
}

// Сбор элементов DOM
function collectDOMElements() {
    elements = {
        // Кнопки
        buyTonBtn: document.getElementById('buy-ton-btn'),
        buyRubBtn: document.getElementById('buy-rub-btn'),
        connectWalletBtn: document.getElementById('connect-wallet-btn'),
        confirmTonBtn: document.getElementById('confirm-ton-btn'),
        confirmRubBtn: document.getElementById('confirm-rub-btn'),
        copyRefBtn: document.getElementById('copy-ref-btn'),
        shareRefBtn: document.getElementById('share-ref-btn'),

        // Модальные окна
        tonModal: document.getElementById('ton-modal'),
        rubModal: document.getElementById('rub-modal'),

        // Изображения виджетов
        tonImage: document.getElementById('ton-widget-image'),
        rubImage: document.getElementById('rub-widget-image'),

        // Формы
        tonStarsInput: document.getElementById('ton-stars'),
        rubStarsInput: document.getElementById('rub-stars'),
        tonPriceDisplay: document.getElementById('ton-price'),
        rubPriceDisplay: document.getElementById('rub-price'),

        // Статус кошелька
        walletStatus: document.getElementById('wallet-status'),
        walletButtons: document.getElementById('wallet-buttons'),

        // Реферальная система
        refLinkInput: document.getElementById('ref-link-input'),
        referralsCount: document.getElementById('referrals-count'),
        earnedAmount: document.getElementById('earned-amount'),

        // Уведомления
        notification: document.getElementById('notification'),

        // Навигация
        navBtns: document.querySelectorAll('.nav-btn'),
        tabContents: document.querySelectorAll('.tab-content'),

        // Вкладки
        marketTab: document.getElementById('market'),
        partnershipTab: document.getElementById('partnership')
    };
}

// Инициализация TON Connect
async function initTonConnect() {
    try {
        // Проверка доступности TonConnectSDK
        if (!window.TonConnect) {
            throw new Error('TonConnect SDK не загружен');
        }

        connector = new TonConnect.TonConnect({
            manifestUrl: CONFIG.MANIFEST_URL
        });

        // Проверка подключения
        if (connector.connected) {
            wallet = connector.account;
            updateWalletStatus();
        }

        // Подписка на изменения
        connector.onStatusChange(wallet => {
            updateWalletStatus(wallet);
        });

        // Обновление кнопок кошельков
        await updateWalletButtons();
    } catch (error) {
        showNotification('Ошибка TON Connect: ' + error.message, 'error');
    }
}

// Обновление кнопок кошельков
async function updateWalletButtons() {
    try {
        const wallets = await connector.getWallets();
        if (!elements.walletButtons) return;

        elements.walletButtons.innerHTML = '';

        wallets.forEach(wallet => {
            const button = document.createElement('button');
            button.className = 'wallet-btn';
            button.textContent = wallet.name;
            button.onclick = () => connectWallet(wallet);
            elements.walletButtons.appendChild(button);
        });
    } catch (error) {
        console.error('Ошибка получения кошельков:', error);
    }
}

// Обновление статуса кошелька
function updateWalletStatus(w = null) {
    if (w) wallet = w;

    if (wallet && elements.walletStatus) {
        elements.walletStatus.textContent = `Кошелёк: ${wallet.name}`;
        elements.connectWalletBtn.textContent = 'Отключить';
    } else if (elements.walletStatus) {
        elements.walletStatus.textContent = 'Кошелёк не подключен';
        elements.connectWalletBtn.textContent = 'Подключить';
    }
}

// Подключение кошелька
async function connectWallet(walletInfo = null) {
    try {
        if (connector.connected) {
            await connector.disconnect();
            wallet = null;
            updateWalletStatus();
            return;
        }

        if (walletInfo) {
            await connector.connect(walletInfo);
        } else {
            const wallets = await connector.getWallets();
            if (wallets.length > 0) {
                await connector.connect(wallets[0]);
            }
        }
    } catch (error) {
        showNotification('Ошибка подключения: ' + error.message, 'error');
    }
}

// Инициализация ЮMoney
function initYooMoney() {
    try {
        if (typeof YooMoneyCheckoutWidget === 'undefined') {
            throw new Error('ЮMoney виджет не загружен');
        }

        window.yooMoneyCheckoutWidget = new YooMoneyCheckoutWidget({
            merchant_id: CONFIG.YOOMONEY_ID,
            language: 'ru',
            theme: 'dark'
        });
    } catch (error) {
        console.error('Ошибка инициализации ЮMoney:', error);
        showNotification('Ошибка платежной системы', 'error');
    }
}

// Покупка за TON
async function buyWithTon() {
    const stars = parseInt(elements.tonStarsInput.value);
    const amount = stars * CONFIG.TON_PRICE;

    if (!connector || !connector.connected) {
        showNotification('Сначала подключите кошелёк', 'error');
        return;
    }

    if (stars < 10) {
        showNotification('Минимальная покупка: 10 звёзд', 'error');
        return;
    }

    try {
        const transaction = {
            validUntil: Math.floor(Date.now() / 1000) + 300,
            messages: [{
                address: 'EQCbaFt3eQy4r7e3Qq1XOyW2N9l5nQvJ2Aiy8G4VZpQkL1bh',
                amount: (amount * 1000000000).toString(),
                payload: `Покупка ${stars} звёзд`
            }]
        };

        showNotification('Подтвердите транзакцию в кошельке...', 'info');
        const result = await connector.sendTransaction(transaction);
        showNotification('Транзакция отправлена!', 'success');

        // Отправка данных на бекенд
        await fetch(`${CONFIG.BACKEND_URL}/process_ton`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                tx_hash: result.boc,
                amount: amount,
                stars: stars
            })
        });

        closeModal(elements.tonModal);
    } catch (error) {
        showNotification('Ошибка: ' + error.message, 'error');
    }
}

// Покупка за RUB
function buyWithRub() {
    const stars = parseInt(elements.rubStarsInput.value);
    const amount = stars * CONFIG.RUB_PRICE;

    if (stars < 1) {
        showNotification('Минимальная покупка: 1 звезда', 'error');
        return;
    }

    try {
        if (!window.yooMoneyCheckoutWidget) {
            throw new Error('Платежный виджет не инициализирован');
        }

        window.yooMoneyCheckoutWidget.amount = amount;
        window.yooMoneyCheckoutWidget.description = `Покупка ${stars} звёзд`;
        window.yooMoneyCheckoutWidget.open();

        window.yooMoneyCheckoutWidget.on('success', () => {
            showNotification('Оплата прошла успешно!', 'success');
            closeModal(elements.rubModal);
        });
    } catch (error) {
        showNotification('Ошибка ЮMoney: ' + error.message, 'error');
    }
}

// Загрузка реферальных данных
async function loadRefData() {
    try {
        // Здесь будет запрос к вашему бекенду
        elements.refLinkInput.value = 'https://t.me/WalletStarsBot?start=ref_12345';
        elements.referralsCount.textContent = '5';
        elements.earnedAmount.textContent = '2.5 TON';
    } catch (error) {
        console.error('Ошибка загрузки реферальных данных:', error);
    }
}

// Копирование реферальной ссылки
function copyRefLink() {
    elements.refLinkInput.select();
    document.execCommand('copy');
    showNotification('Ссылка скопирована!', 'success');
}

// Поделиться ссылкой
function shareRefLink() {
    if (navigator.share) {
        navigator.share({
            title: 'Присоединяйся к WalletStars!',
            text: 'Получай бонусы за покупки звёзд',
            url: elements.refLinkInput.value
        });
    } else {
        copyRefLink();
    }
}

// Открытие модального окна
function openModal(modal) {
    modal.classList.add('active');
}

// Закрытие модального окна
function closeModal(modal) {
    modal.classList.remove('active');
}

// Показать уведомление
function showNotification(message, type = 'info') {
    if (!elements.notification) return;

    elements.notification.textContent = message;
    elements.notification.className = 'notification';
    elements.notification.classList.add(type, 'show');

    setTimeout(() => {
        elements.notification.classList.remove('show');
    }, 3000);
}

// Обновление цен
function updatePrices() {
    const tonStars = parseInt(elements.tonStarsInput.value) || 0;
    const rubStars = parseInt(elements.rubStarsInput.value) || 0;

    if (elements.tonPriceDisplay) {
        elements.tonPriceDisplay.textContent = (tonStars * CONFIG.TON_PRICE).toFixed(2);
    }

    if (elements.rubPriceDisplay) {
        elements.rubPriceDisplay.textContent = (rubStars * CONFIG.RUB_PRICE).toFixed(2);
    }
}

// Настройка обработчиков событий
function setupEventListeners() {
    // Кнопки покупки
    if (elements.buyTonBtn) {
        elements.buyTonBtn.addEventListener('click', () => openModal(elements.tonModal));
    }

    if (elements.buyRubBtn) {
        elements.buyRubBtn.addEventListener('click', () => openModal(elements.rubModal));
    }

    // Кнопки подтверждения покупки
    if (elements.confirmTonBtn) {
        elements.confirmTonBtn.addEventListener('click', buyWithTon);
    }

    if (elements.confirmRubBtn) {
        elements.confirmRubBtn.addEventListener('click', buyWithRub);
    }

    // Кнопка подключения кошелька
    if (elements.connectWalletBtn) {
        elements.connectWalletBtn.addEventListener('click', () => connectWallet());
    }

    // Реферальные кнопки
    if (elements.copyRefBtn) {
        elements.copyRefBtn.addEventListener('click', copyRefLink);
    }

    if (elements.shareRefBtn) {
        elements.shareRefBtn.addEventListener('click', shareRefLink);
    }

    // Закрытие модальных окон
    document.querySelectorAll('.close-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) closeModal(modal);
        });
    });

    // Навигация между вкладками
    if (elements.navBtns) {
        elements.navBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                const tabId = this.dataset.tab;

                // Обновление активной кнопки
                elements.navBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');

                // Показать активный контент
                elements.tabContents.forEach(content => content.classList.remove('active'));
                document.getElementById(tabId).classList.add('active');

                // Загружаем реферальные данные при переходе на вкладку партнерства
                if (tabId === 'partnership') {
                    loadRefData();
                }
            });
        });
    }

    // Обновление цен при изменении количества звезд
    if (elements.tonStarsInput) {
        elements.tonStarsInput.addEventListener('input', updatePrices);
    }

    if (elements.rubStarsInput) {
        elements.rubStarsInput.addEventListener('input', updatePrices);
    }

    // Закрытие модалок при клике вне контента
    window.addEventListener('click', (event) => {
        if (elements.tonModal && event.target === elements.tonModal) {
            closeModal(elements.tonModal);
        }
        if (elements.rubModal && event.target === elements.rubModal) {
            closeModal(elements.rubModal);
        }
    });
}

// Запуск приложения
document.addEventListener('DOMContentLoaded', initApp);