/* Camada de dados da landing page — implementação do plano de tracking
 * (tracking/plano_de_tracking.md). Nada aqui envia dados para servidor algum:
 * os eventos vão para window.dataLayer, que um container GTM leria em produção.
 */
(function () {
  'use strict';
  const dl = (window.dataLayer = window.dataLayer || []);
  const ls = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* modo privado */ } },
  };
  const ss = {
    get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { /* modo privado */ } },
  };

  // ---------------------------------------------------------------- UTM: captura e persistência na sessão
  const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'gclid', 'fbclid'];
  const qs = new URLSearchParams(location.search);
  const utm = {};
  UTM_KEYS.forEach((k) => {
    const v = qs.get(k);
    if (v) utm[k] = k.startsWith('utm_') ? v.trim().toLowerCase() : v; // normaliza já na origem
  });
  if (Object.keys(utm).length) ss.set('aurum_utm', JSON.stringify(utm));
  const utmSessao = JSON.parse(ss.get('aurum_utm') || '{}');

  // ---------------------------------------------------------------- helpers
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
  function push(event, params = {}) {
    const payload = Object.assign({ event, event_id: uuid(), page_path: location.pathname + location.hash }, params);
    dl.push(payload);
    mostrar(payload);
  }

  // ---------------------------------------------------------------- debug panel
  const log = document.getElementById('log');
  function mostrar(obj) {
    if (!log) return;
    const li = document.createElement('li');
    const { event, event_id, ...resto } = obj;
    li.innerHTML = `<b>${event}</b><pre>${JSON.stringify(resto, null, 1)}</pre>`;
    log.prepend(li);
  }
  document.getElementById('limpar')?.addEventListener('click', () => (log.innerHTML = ''));

  // ---------------------------------------------------------------- consentimento (Consent Mode v2)
  const consentBox = document.getElementById('consent');
  function aplicarConsent(escolha) {
    const sim = escolha === 'todos';
    gtag('consent', 'update', {
      analytics_storage: sim ? 'granted' : 'denied',
      ad_storage: sim ? 'granted' : 'denied',
      ad_user_data: sim ? 'granted' : 'denied',
      ad_personalization: sim ? 'granted' : 'denied',
    });
    ls.set('aurum_consent', escolha);
    consentBox.hidden = true;
    push('consent_update', { consent_choice: escolha });
  }
  const consentSalvo = ls.get('aurum_consent');
  if (consentSalvo) { consentBox.hidden = true; aplicarConsent(consentSalvo); }
  document.getElementById('aceitar').addEventListener('click', () => aplicarConsent('todos'));
  document.getElementById('essenciais').addEventListener('click', () => aplicarConsent('essenciais'));

  // ---------------------------------------------------------------- page_view virtual + contexto
  push('page_context', {
    page_type: 'landing',
    traffic_utm_source: utmSessao.utm_source || null,
    traffic_utm_medium: utmSessao.utm_medium || null,
    traffic_utm_campaign: utmSessao.utm_campaign || null,
    has_gclid: Boolean(utmSessao.gclid),
  });

  // ---------------------------------------------------------------- impressão de promoção (IntersectionObserver)
  const promo = document.querySelector('[data-promo]');
  if (promo && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((ents) => {
      ents.forEach((e) => {
        if (e.isIntersecting) {
          push('view_promotion', { promotion_name: promo.dataset.promo, creative_slot: 'hero' });
          io.disconnect();
        }
      });
    }, { threshold: 0.6 });
    io.observe(promo);
  }

  // ---------------------------------------------------------------- scroll 50/90
  const marcas = new Set();
  addEventListener('scroll', () => {
    const pct = (scrollY + innerHeight) / document.documentElement.scrollHeight;
    [50, 90].forEach((m) => {
      if (pct * 100 >= m && !marcas.has(m)) { marcas.add(m); push('scroll_depth', { percent_scrolled: m }); }
    });
  }, { passive: true });

  // ---------------------------------------------------------------- app download
  document.querySelectorAll('[data-app]').forEach((b) =>
    b.addEventListener('click', () => {
      const android = /android/i.test(navigator.userAgent);
      push('app_download_click', { cta_location: b.dataset.app, store: android ? 'play_store' : 'app_store' });
    }));

  // ---------------------------------------------------------------- onboarding com teste A/B
  let variante = ls.get('aurum_exp_onboarding');
  if (!variante) {
    variante = Math.random() < 0.5 ? 'v1_3_etapas' : 'v2_2_etapas';
    ls.set('aurum_exp_onboarding', variante);
  }
  const ETAPAS = {
    v1_3_etapas: [
      { nome: 'dados_pessoais', titulo: 'Seus dados', campos: [['nome', 'Nome completo', 'text'], ['cpf', 'CPF', 'text'], ['celular', 'Celular', 'tel']] },
      { nome: 'endereco_renda', titulo: 'Endereço e renda', campos: [['cep', 'CEP', 'text'], ['renda', 'Renda mensal (R$)', 'number']] },
      { nome: 'documentos', titulo: 'Documento', campos: [['selfie', 'Selfie com documento (simulado)', 'checkbox']] },
    ],
    v2_2_etapas: [
      { nome: 'dados_pessoais', titulo: 'Seus dados', campos: [['nome', 'Nome completo', 'text'], ['cpf', 'CPF', 'text'], ['celular', 'Celular', 'tel']] },
      { nome: 'documentos', titulo: 'Documento', campos: [['selfie', 'Selfie com documento (simulado)', 'checkbox']] },
    ],
  };
  const etapas = ETAPAS[variante];
  let etapaAtual = 0;
  let iniciou = false;
  const sec = document.getElementById('abrir-conta');
  const form = document.getElementById('form');
  document.getElementById('variante').textContent = variante;

  function cpfValido(c) {
    c = (c || '').replace(/\D/g, '');
    if (c.length !== 11 || /^(\d)\1+$/.test(c)) return false;
    let s = 0;
    for (let i = 0; i < 9; i++) s += +c[i] * (10 - i);
    let d = (s * 10) % 11 % 10;
    if (d !== +c[9]) return false;
    s = 0;
    for (let i = 0; i < 10; i++) s += +c[i] * (11 - i);
    return (s * 10) % 11 % 10 === +c[10];
  }

  function render() {
    document.getElementById('passos').innerHTML = etapas
      .map((e, i) => `<li class="${i < etapaAtual ? 'ok' : i === etapaAtual ? 'atual' : ''}">${e.titulo}</li>`).join('');
    const e = etapas[etapaAtual];
    form.innerHTML = e.campos.map(([id, rot, tipo]) => tipo === 'checkbox'
      ? `<label class="check"><input type="checkbox" id="${id}"> ${rot}</label>`
      : `<label>${rot}<input id="${id}" type="${tipo}" autocomplete="off"></label>`).join('') +
      `<p class="erro" id="erro" hidden></p><button class="btn" type="submit">${etapaAtual === etapas.length - 1 ? 'Enviar cadastro' : 'Continuar'}</button>`;
  }

  function abrirOnboarding(local) {
    push('cta_click', { cta_location: local, cta_text: 'Abrir minha conta' });
    sec.hidden = false;
    sec.scrollIntoView({ behavior: 'smooth' });
    if (!iniciou) {
      iniciou = true;
      push('begin_onboarding', { form_variant: variante, experiment_onboarding: variante });
    }
    render();
  }
  document.querySelectorAll('[data-cta]').forEach((b) => b.addEventListener('click', () => abrirOnboarding(b.dataset.cta)));

  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const e = etapas[etapaAtual];
    let erro = null;
    for (const [id, , tipo] of e.campos) {
      const el = document.getElementById(id);
      if (tipo === 'checkbox' ? !el.checked : !el.value.trim()) { erro = id; break; }
      if (id === 'cpf' && !cpfValido(el.value)) { erro = 'cpf'; break; }
    }
    if (erro) {
      const p = document.getElementById('erro');
      p.textContent = erro === 'cpf' ? 'CPF inválido (use um CPF de teste válido)' : 'Preencha este campo';
      p.hidden = false;
      // nunca envie o VALOR digitado para o analytics (PII), só o nome do campo
      push('form_error', { step_number: etapaAtual + 1, error_field: erro, form_variant: variante });
      return;
    }
    push('onboarding_step_complete', { step_number: etapaAtual + 1, step_name: e.nome, form_variant: variante });
    etapaAtual += 1;
    if (etapaAtual < etapas.length) { render(); return; }
    // sign_up: o user_id é um hash gerado no servidor em produção; aqui, um id aleatório
    push('sign_up', { method: 'onboarding_web', account_type: 'conta_digital', form_variant: variante,
                      user_id: 'demo_' + uuid().slice(0, 8) });
    form.innerHTML = '<p class="sucesso">Cadastro simulado enviado! Veja no painel ao lado a sequência completa de eventos.</p>';
    document.getElementById('passos').querySelectorAll('li').forEach((li) => (li.className = 'ok'));
  });
})();
