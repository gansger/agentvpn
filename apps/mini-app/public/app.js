const state = {
  csrfToken: null,
  user: null,
  plans: [],
  selectedPlan: null,
  payment: null,
  subscription: null,
};

const fallbackPlans = [
  { id: 1, name: "1 месяц", duration_days: 30, price: "150", currency: "RUB" },
  { id: 2, name: "3 месяца", duration_days: 90, price: "380", currency: "RUB", popular: true },
  { id: 3, name: "12 месяцев", duration_days: 365, price: "1260", currency: "RUB" },
];

const telegram = window.Telegram?.WebApp;
const publicInfo = window.AGENTVPN_PUBLIC_INFO || {};
if (telegram?.initData) document.body.classList.add("telegram-mode");
telegram?.ready();
telegram?.expand();

function populatePublicInfo() {
  document.querySelectorAll("[data-public-field]").forEach((element) => {
    const value = publicInfo[element.dataset.publicField];
    element.textContent = value || "Требуется заполнить до публикации";
    element.classList.toggle("missing-public-info", !value);
  });
  document.querySelectorAll("[data-public-link]").forEach((element) => {
    const value = publicInfo[element.dataset.publicLink];
    if (value) element.href = value;
    element.classList.toggle("missing-public-info", !value);
  });
  const supportEmail = document.querySelector("#mini-support-email");
  if (supportEmail && publicInfo.supportEmail) {
    supportEmail.href = `mailto:${publicInfo.supportEmail}`;
    supportEmail.querySelector("small").textContent = publicInfo.supportEmail;
  }
}

function money(value) {
  return `${Number(value).toLocaleString("ru-RU")} ₽`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "include",
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Сервис временно недоступен");
  }
  return response.status === 204 ? null : response.json();
}

async function authenticateTelegram() {
  if (!telegram?.initData) return;
  try {
    const auth = await api("/api/auth/telegram", {
      method: "POST",
      body: JSON.stringify({ init_data: telegram.initData }),
    });
    state.csrfToken = auth.csrf_token;
    state.user = auth.user;
    document.querySelector("#app-notice")?.classList.add("authenticated");
    document.querySelector("#profile-name").textContent = auth.user.first_name || "Профиль";
    document.querySelector("#profile-handle").textContent = auth.user.username ? `@${auth.user.username}` : "AGentVPN";
    await loadSubscription();
  } catch (error) {
    showNotice(error.message);
  }
}

async function loadPlans() {
  try {
    const plans = await api("/api/plans");
    state.plans = plans.length ? plans : fallbackPlans;
  } catch {
    state.plans = fallbackPlans;
  }
  renderAppPlans();
  renderPublicPlans();
}

async function loadSubscription() {
  try {
    state.subscription = await api("/api/subscription/current");
    document.querySelector("#profile-plan").textContent = `Тариф #${state.subscription.plan_id}`;
    document.querySelector("#profile-status").textContent =
      `Активен до ${new Date(state.subscription.expires_at).toLocaleDateString("ru-RU")}`;
  } catch {
    state.subscription = null;
  }
}

function renderAppPlans() {
  const container = document.querySelector("#app-plans");
  if (!container) return;
  container.innerHTML = state.plans.map((plan, index) => `
    <article class="app-plan ${plan.popular || index === 1 ? "popular" : ""}">
      ${plan.popular || index === 1 ? '<span class="tag">Популярный</span>' : ""}
      <header><div><h2>${escapeHtml(plan.name)}</h2><small>${plan.duration_days} дней</small></div><b>${money(plan.price)}</b></header>
      <ul><li>Hysteria2 и VLESS REALITY</li><li>Поддержка всех устройств</li></ul>
      <button class="button select-plan" data-plan-id="${plan.id}">Выбрать</button>
    </article>`).join("");
  container.querySelectorAll(".select-plan").forEach((button) =>
    button.addEventListener("click", () => selectPlan(Number(button.dataset.planId))));
}

function renderPublicPlans() {
  const buttons = document.querySelectorAll(".choose-plan");
  buttons.forEach((button, index) => {
    const plan = state.plans[index];
    if (!plan) return;
    button.dataset.planId = plan.id;
    button.dataset.planName = plan.name;
    button.dataset.planPrice = plan.price;
  });
}

function selectPlan(planId) {
  state.selectedPlan = state.plans.find((plan) => Number(plan.id) === Number(planId)) || fallbackPlans[0];
  document.querySelector("#checkout-plan").textContent = state.selectedPlan.name;
  document.querySelector("#checkout-old-price").textContent = money(state.selectedPlan.price);
  document.querySelector("#checkout-price").textContent = money(state.selectedPlan.price);
  document.querySelector("#waiting-price").textContent = money(state.selectedPlan.price);
  route("checkout");
}

async function createCheckout() {
  if (!document.querySelector("#agreement").checked) {
    showNotice("Подтвердите согласие с условиями оказания услуг.");
    return;
  }
  if (!state.user || !state.csrfToken) {
    showNotice("Для безопасной покупки откройте AGentVPN внутри Telegram Mini App.");
    telegram?.showAlert?.("Откройте приложение через Telegram-бот AGentVPN.");
    return;
  }
  const button = document.querySelector("#checkout-button");
  button.disabled = true;
  button.textContent = "Создаём платёж…";
  try {
    state.payment = await api("/api/checkout/robokassa", {
      method: "POST",
      headers: {
        "X-CSRF-Token": state.csrfToken,
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ plan_id: state.selectedPlan.id }),
    });
    document.querySelector("#waiting-order").textContent = state.payment.id.slice(0, 8);
    route("waiting");
    telegram?.openLink ? telegram.openLink(state.payment.payment_url) : window.location.assign(state.payment.payment_url);
  } catch (error) {
    showNotice(error.message);
  } finally {
    button.disabled = false;
    button.innerHTML = 'Оплатить через СБП <svg><use href="#i-shield"/></svg>';
  }
}

async function checkPayment() {
  if (!state.payment) return showNotice("Платёж ещё не создан.");
  try {
    state.payment = await api(`/api/payments/${state.payment.id}`);
    if (state.payment.status === "success") {
      await loadSubscription();
      route("connection");
      telegram?.HapticFeedback?.notificationOccurred("success");
    } else {
      showNotice(`Статус платежа: ${state.payment.status}`);
    }
  } catch (error) {
    showNotice(error.message);
  }
}

function route(target) {
  document.querySelectorAll(".app-view").forEach((view) => view.classList.toggle("active", view.dataset.view === target));
  document.querySelectorAll(".app-nav .app-route").forEach((button) => button.classList.toggle("active", button.dataset.target === target));
  window.scrollTo({ top: 0, behavior: "smooth" });
  telegram?.HapticFeedback?.selectionChanged();
}

function showNotice(message) {
  const notice = document.querySelector("#app-notice");
  if (!notice) return;
  notice.textContent = message;
  notice.classList.remove("authenticated");
}

function showSiteToast(message) {
  const toast = document.querySelector("#site-toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("visible");
  window.setTimeout(() => toast.classList.remove("visible"), 4200);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

document.querySelector("#registration-form")?.addEventListener("submit", (event) => {
  event.preventDefault();
  const status = document.querySelector("#registration-status");
  if (!document.querySelector("#registration-consent")?.checked) {
    status.textContent = "Для регистрации необходимо принять публичные документы.";
    return;
  }
  if (!publicInfo.telegramUrl) {
    status.textContent = "Ссылка на Telegram Mini App ещё не опубликована.";
    return;
  }
  window.location.assign(publicInfo.telegramUrl);
});

document.querySelectorAll(".app-route").forEach((button) =>
  button.addEventListener("click", () => route(button.dataset.target)));
document.querySelectorAll(".choose-plan").forEach((button) =>
  button.addEventListener("click", () => {
    if (window.innerWidth > 900) {
      showSiteToast("Для оформления заказа откройте AGentVPN внутри Telegram Mini App.");
      return;
    }
    selectPlan(Number(button.dataset.planId));
  }));
document.querySelector("#checkout-button")?.addEventListener("click", createCheckout);
document.querySelector("#check-payment")?.addEventListener("click", checkPayment);

loadPlans();
authenticateTelegram();
populatePublicInfo();
