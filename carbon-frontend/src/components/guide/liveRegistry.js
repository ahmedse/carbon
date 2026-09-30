// Live cards: how the coach shows the object a lesson is about.
// The engine names a kind (`identity`, `period`, ...); an app that owns a kind drops
// `apps/<id>/guideLive.jsx` and calls registerLiveCard. Nothing here knows a domain.
const CARDS = new Map();

export function registerLiveCard(kind, Component) {
  CARDS.set(kind, Component);
}

export function getLiveCard(kind) {
  return CARDS.get(kind) || null;
}
