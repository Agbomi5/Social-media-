/* Frontend app.js — vanilla JS for the Django backend.
   Adjust BASE_URL if your backend runs elsewhere. */
(function () {
  const cfg = window.__APP_CONFIG__ || {};
  const rawBase = cfg.API_BASE_URL || window.location.origin;
  const BASE_URL = rawBase.replace(/\/+$/, '');

  const ACCESS_TOKEN_KEY = 'access_token';
  const REFRESH_TOKEN_KEY = 'refresh_token';
  const ENDPOINTS = {
    index: `${BASE_URL}/api/v1/feed/`,
    upload: `${BASE_URL}/api/v1/upload/`,
    signin: `${BASE_URL}/api/v1/signin/`,
    signup: `${BASE_URL}/api/v1/signup/`,
    token: `${BASE_URL}/api/v1/auth/token/`,
    settings: `${BASE_URL}/api/v1/settings/`,
    passwordChange: `${BASE_URL}/api/v1/settings/password/`,
    profile: (username) => `${BASE_URL}/api/v1/profile/${encodeURIComponent(username)}/`,
    like: (id) => `${BASE_URL}/api/v1/posts/${id}/like/`,
    comment: (id) => `${BASE_URL}/api/v1/posts/${id}/comments/`,
    commentDetail: (id) => `${BASE_URL}/api/v1/comments/${id}/`,
    commentLike: (id) => `${BASE_URL}/api/v1/comments/${id}/like/`,
    commentSticker: (id) => `${BASE_URL}/api/v1/comments/${id}/sticker/`,
    delete: (id) => `${BASE_URL}/api/v1/posts/${id}/delete/`,
    edit: (id) => `${BASE_URL}/api/v1/posts/${id}/edit/`,
    bookmarks: `${BASE_URL}/api/v1/bookmarks/`,
    bookmarkCreate: `${BASE_URL}/api/v1/bookmarks/create/`,
    bookmarkDelete: (id) => `${BASE_URL}/api/v1/bookmarks/${id}/`,
    notifications: `${BASE_URL}/api/v1/notifications/`,
    notificationsUnread: `${BASE_URL}/api/v1/notifications/unread-count/`,
    messages: `${BASE_URL}/api/v1/messages/`,
    messagesUnread: `${BASE_URL}/api/v1/messages/unread-count/`,
    messageDelete: (id) => `${BASE_URL}/api/v1/messages/${id}/delete/`,
    messageEdit: (id) => `${BASE_URL}/api/v1/messages/${id}/edit/`,
    conversationList: `${BASE_URL}/api/v1/conversations/`,
    conversationRead: (username) => `${BASE_URL}/api/v1/conversation/${encodeURIComponent(username)}/read/`,
    conversationTyping: (username) => `${BASE_URL}/api/v1/conversation/${encodeURIComponent(username)}/typing/`,
    stickers: `${BASE_URL}/api/v1/stickers/defaults/`,
    trending: `${BASE_URL}/api/v1/trending/`,
    suggested: `${BASE_URL}/api/v1/suggested/`,
    search: `${BASE_URL}/api/v1/search/`,
    follow: (username) => `${BASE_URL}/api/v1/profile/${encodeURIComponent(username)}/follow/`,
    conversation: (username) => `${BASE_URL}/api/v1/conversation/${encodeURIComponent(username)}/`,
    conversationSend: (username) => `${BASE_URL}/api/v1/conversation/${encodeURIComponent(username)}/send/`,
  };

  window.__APP__ = { BASE_URL, ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, ENDPOINTS };
})();

// Default sticker catalog (matches the backend DEFAULT_REACTIONS)
const STICKER_CATALOG = [
  { name: 'Like', emoji: '👍' },
  { name: 'Love', emoji: '❤️' },
  { name: 'Haha', emoji: '😂' },
  { name: 'Wow', emoji: '😮' },
  { name: 'Sad', emoji: '😢' },
  { name: 'Angry', emoji: '😡' },
];
let stickerIdByName = {}; // populated by loadStickers()
let currentUser = '';
let currentEmail = '';

function pageUrl(page) {
  return page.startsWith('/') ? page : `/${page}`;
}

function goTo(page) {
  window.location.assign(pageUrl(page));
}

function readAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || localStorage.getItem('token') || '';
}

function saveTokens(data) {
  if (data.access) localStorage.setItem(ACCESS_TOKEN_KEY, data.access);
  if (data.refresh) localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh);
}

function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem('token');
}

function buildUrl(path) {
  return path.startsWith('http') ? path : `${BASE_URL}${path}`;
}

async function apiRequest(path, opts = {}) {
  const url = buildUrl(path);
  const headers = new Headers(opts.headers || {});
  const csrf = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='));
  if (csrf) {
    headers.set('X-CSRFToken', csrf.split('=')[1]);
  }
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  const res = await fetch(url, { ...opts, headers, credentials: 'include' });
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch (e) { data = text; }
  }
  if (!res.ok) {
    const errorDetail = data && (data.detail || data.error || data.message || data);
    let message = res.statusText || 'Request failed';
    if (typeof errorDetail === 'string') {
      message = errorDetail;
    } else if (typeof errorDetail === 'object' && errorDetail !== null) {
      message = Object.entries(errorDetail)
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
        .join(' | ');
    }
    if (res.status === 401 || res.status === 403) {
      clearTokens();
      if (window.location.pathname.split('/').pop() !== 'signin.html') {
        goTo('signin.html');
      }
    }
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

async function authFetch(path, opts = {}) {
  const token = readAccessToken();
  const headers = new Headers(opts.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  headers.set('Accept', 'application/json');
  return apiRequest(path, { ...opts, headers });
}

function md5(string) {
  function rotateLeft(lValue, iShiftBits) {
    return (lValue << iShiftBits) | (lValue >>> (32 - iShiftBits));
  }
  function addUnsigned(lX, lY) {
    let lX4, lY4, lX8, lY8, lResult;
    lX8 = lX & 0x80000000;
    lY8 = lY & 0x80000000;
    lX4 = lX & 0x40000000;
    lY4 = lY & 0x40000000;
    lResult = (lX & 0x3FFFFFFF) + (lY & 0x3FFFFFFF);
    if (lX4 & lY4) return lResult ^ 0x80000000 ^ lX8 ^ lY8;
    if (lX4 | lY4) {
      if (lResult & 0x40000000) return lResult ^ 0xC0000000 ^ lX8 ^ lY8;
      return lResult ^ 0x40000000 ^ lX8 ^ lY8;
    }
    return lResult ^ lX8 ^ lY8;
  }
  function F(x, y, z) { return (x & y) | (~x & z); }
  function G(x, y, z) { return (x & z) | (y & ~z); }
  function H(x, y, z) { return x ^ y ^ z; }
  function I(x, y, z) { return y ^ (x | ~z); }
  function FF(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(F(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function GG(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(G(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function HH(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(H(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function II(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(I(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function convertToWordArray(str) {
    const lWordCount = [];
    let lMessageLength = str.length;
    let lNumberOfWordsTemp1 = lMessageLength + 8;
    let lNumberOfWordsTemp2 = (lNumberOfWordsTemp1 - (lNumberOfWordsTemp1 % 64)) / 64;
    let lNumberOfWords = (lNumberOfWordsTemp2 + 1) * 16;
    let lBytePosition = 0;
    let lByteCount = 0;
    while (lByteCount < lMessageLength) {
      const lWordCountIndex = (lByteCount - (lByteCount % 4)) / 4;
      lWordCount[lWordCountIndex] = lWordCount[lWordCountIndex] | (str.charCodeAt(lByteCount) << ((lByteCount % 4) * 8));
      lByteCount++;
    }
    const lWordCountIndex = (lByteCount - (lByteCount % 4)) / 4;
    lWordCount[lWordCountIndex] = lWordCount[lWordCountIndex] | (0x80 << ((lByteCount % 4) * 8));
    lWordCount[lNumberOfWords - 2] = lMessageLength << 3;
    lWordCount[lNumberOfWords - 1] = lMessageLength >>> 29;
    return lWordCount;
  }
  function wordToHex(lValue) {
    let wordToHexValue = '';
    for (let lCount = 0; lCount <= 3; lCount++) {
      const lByte = (lValue >>> (lCount * 8)) & 255;
      let lHex = lByte.toString(16);
      if (lHex.length === 1) lHex = '0' + lHex;
      wordToHexValue += lHex;
    }
    return wordToHexValue;
  }
  let x = [];
  let k, AA, BB, CC, DD, a, b, c, d;
  x = convertToWordArray(string);
  a = 0x67452301;
  b = 0xEFCDAB89;
  c = 0x98BADCFE;
  d = 0x10325476;
  for (k = 0; k < x.length; k += 16) {
    AA = a;
    BB = b;
    CC = c;
    DD = d;
    a = FF(a, b, c, d, x[k + 0], 7, 0xD76AA478);
    a = FF(a, b, c, d, x[k + 1], 12, 0xE8C7B756);
    a = FF(a, b, c, d, x[k + 2], 17, 0x242070DB);
    a = FF(a, b, c, d, x[k + 3], 22, 0xC1BDCEEE);
    a = FF(a, b, c, d, x[k + 4], 7, 0xF57C0FAF);
    a = FF(a, b, c, d, x[k + 5], 12, 0x4787C62A);
    a = FF(a, b, c, d, x[k + 6], 17, 0xA8304613);
    a = FF(a, b, c, d, x[k + 7], 22, 0xFD469501);
    a = FF(a, b, c, d, x[k + 8], 7, 0x698098D8);
    a = FF(a, b, c, d, x[k + 9], 12, 0x8B44F7AF);
    a = FF(a, b, c, d, x[k + 10], 17, 0xFFFF5BB1);
    a = FF(a, b, c, d, x[k + 11], 22, 0x895CD7BE);
    a = FF(a, b, c, d, x[k + 12], 7, 0x6B901122);
    a = FF(a, b, c, d, x[k + 13], 12, 0xFD987193);
    a = FF(a, b, c, d, x[k + 14], 17, 0xA679438E);
    a = FF(a, b, c, d, x[k + 15], 22, 0x49B40821);
    a = GG(a, b, c, d, x[k + 1], 5, 0xF61E2562);
    a = GG(a, b, c, d, x[k + 6], 9, 0xC040B340);
    a = GG(a, b, c, d, x[k + 11], 14, 0x265E5A51);
    a = GG(a, b, c, d, x[k + 0], 20, 0xE9B6C7AA);
    a = GG(a, b, c, d, x[k + 5], 5, 0xD62F105D);
    a = GG(a, b, c, d, x[k + 10], 9, 0x02441453);
    a = GG(a, b, c, d, x[k + 15], 14, 0xD8A1E681);
    a = GG(a, b, c, d, x[k + 4], 20, 0xE7D3FBC8);
    a = GG(a, b, c, d, x[k + 9], 5, 0x21E1CDE6);
    a = GG(a, b, c, d, x[k + 14], 9, 0xC33707D6);
    a = GG(a, b, c, d, x[k + 3], 14, 0xF4D50D87);
    a = GG(a, b, c, d, x[k + 8], 20, 0x455A14ED);
    a = GG(a, b, c, d, x[k + 13], 5, 0xA9E3E905);
    a = GG(a, b, c, d, x[k + 2], 9, 0xFCEFA3F8);
    a = GG(a, b, c, d, x[k + 7], 14, 0x676F02D9);
    a = GG(a, b, c, d, x[k + 12], 20, 0x8D2A4C8A);
    a = HH(a, b, c, d, x[k + 5], 4, 0xFFFA3942);
    a = HH(a, b, c, d, x[k + 8], 11, 0x8771F681);
    a = HH(a, b, c, d, x[k + 11], 16, 0x6D9D6122);
    a = HH(a, b, c, d, x[k + 14], 23, 0xFDE5380C);
    a = HH(a, b, c, d, x[k + 1], 4, 0xA4BEEA44);
    a = HH(a, b, c, d, x[k + 4], 11, 0x4BDECFA9);
    a = HH(a, b, c, d, x[k + 7], 16, 0xF6BB4B60);
    a = HH(a, b, c, d, x[k + 10], 23, 0xBEBFBC70);
    a = HH(a, b, c, d, x[k + 13], 4, 0x289B7EC6);
    a = HH(a, b, c, d, x[k + 0], 11, 0xEAA127FA);
    a = HH(a, b, c, d, x[k + 3], 16, 0xD4EF3085);
    a = HH(a, b, c, d, x[k + 6], 23, 0x04881D05);
    a = HH(a, b, c, d, x[k + 9], 4, 0xD9D4D039);
    a = HH(a, b, c, d, x[k + 12], 11, 0xE6DB99E5);
    a = HH(a, b, c, d, x[k + 15], 16, 0x1FA27CF8);
    a = HH(a, b, c, d, x[k + 2], 23, 0xC4AC5665);
    a = II(a, b, c, d, x[k + 0], 6, 0xF4292244);
    a = II(a, b, c, d, x[k + 7], 10, 0x432AFF97);
    a = II(a, b, c, d, x[k + 14], 15, 0xAB9423A7);
    a = II(a, b, c, d, x[k + 5], 21, 0xFC93A039);
    a = II(a, b, c, d, x[k + 12], 6, 0x655B59C3);
    a = II(a, b, c, d, x[k + 3], 10, 0x8F0CCC92);
    a = II(a, b, c, d, x[k + 10], 15, 0xFFEFF47D);
    a = II(a, b, c, d, x[k + 1], 21, 0x85845DD1);
    a = II(a, b, c, d, x[k + 8], 6, 0x6FA87E4F);
    a = II(a, b, c, d, x[k + 15], 10, 0xFE2CE6E0);
    a = II(a, b, c, d, x[k + 6], 15, 0xA3014314);
    a = II(a, b, c, d, x[k + 13], 21, 0x4E0811A1);
    a = II(a, b, c, d, x[k + 4], 6, 0xF7537E82);
    a = II(a, b, c, d, x[k + 11], 10, 0xBD3AF235);
    a = II(a, b, c, d, x[k + 2], 15, 0x2AD7D2BB);
    a = II(a, b, c, d, x[k + 9], 21, 0xEB86D391);
    a = addUnsigned(a, AA);
    b = addUnsigned(b, BB);
    c = addUnsigned(c, CC);
    d = addUnsigned(d, DD);
  }
  return wordToHex(a) + wordToHex(b) + wordToHex(c) + wordToHex(d);
}

function getGravatarUrl(email, size = 80) {
  const trimmed = (email || '').trim().toLowerCase();
  if (!trimmed) return `https://www.gravatar.com/avatar/?d=identicon&s=${size}`;
  return `https://www.gravatar.com/avatar/${md5(trimmed)}?d=identicon&s=${size}`;
}

function setNavUser(username, email, imageUrl) {
  currentUser = username || '';
  currentEmail = email || '';
  const avatar = document.getElementById('header-avatar');
  const feedAvatar = document.getElementById('feed-avatar');
  const createAvatar = document.getElementById('create-post-avatar');
  const createUsername = document.getElementById('create-post-username');
  const url = imageUrl || getGravatarUrl(email || '');
  if (avatar) avatar.src = url;
  if (feedAvatar) feedAvatar.src = url;
  if (createAvatar) createAvatar.src = url;
  if (createUsername) createUsername.textContent = username || '';
}

function setFeedback(el, message, isError = false) {
  if (!el) return;
  el.textContent = message || '';
  el.classList.remove('error', 'success');
  if (message) el.classList.add(isError ? 'error' : 'success');
}

function timeAgo(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

function buildReactionPicker() {
  const picker = document.createElement('div');
  picker.className = 'reaction-picker';
  STICKER_CATALOG.forEach((s) => {
    const span = document.createElement('span');
    span.className = 'picker-emoji';
    span.textContent = s.emoji;
    span.title = s.name;
    span.dataset.sticker = s.name;
    span.dataset.emoji = s.emoji;
    picker.appendChild(span);
  });
  return picker;
}

function updateReactionSummary(node, post) {
  const bar = node.querySelector('.reaction-bar');
  if (!bar) return;
  bar.innerHTML = '';
  const reactions = post.reactions || [];
  const counts = post.reaction_counts || {};
  if (!reactions.length && !Object.keys(counts).length) return;
  const totalCount = post.total_reactions || 0;
  const summary = document.createElement('div');
  summary.className = 'reaction-summary';
  // Show top 3 emojis + total
  const top = reactions
    .slice()
    .sort((a, b) => (counts[b.sticker_id] || b.count || 0) - (counts[a.sticker_id] || a.count || 0))
    .slice(0, 3);
  top.forEach((r) => {
    const span = document.createElement('span');
    span.className = 'reaction-emoji';
    span.textContent = r.emoji || '👍';
    summary.appendChild(span);
  });
  const total = document.createElement('span');
  total.textContent = `${totalCount}`;
  summary.appendChild(total);
  bar.appendChild(summary);
}

function updateLikeButton(btn, post) {
  const userStickerName = post.user_sticker || null;
  const isLiked = !!post.is_liked;
  btn.classList.toggle('liked', isLiked);
  btn.setAttribute('aria-pressed', isLiked ? 'true' : 'false');
  btn.dataset.sticker = userStickerName || '';
  const stickerEmoji = (STICKER_CATALOG.find((s) => s.name === userStickerName) || {}).emoji || '👍';
  btn.querySelector('.icon').textContent = isLiked ? stickerEmoji : '👍';
  btn.querySelector('.label').textContent = isLiked ? userStickerName || 'Liked' : 'Like';
  btn.querySelector('.count').textContent = post.total_reactions || 0;
}

function renderPost(post) {
  const tpl = document.getElementById('tpl-post');
  if (!tpl) return null;

  const node = tpl.content.firstElementChild.cloneNode(true);
  node.dataset.id = post.id;
  const authorName = typeof post.username === 'object' ? post.username.username : (post.username || 'Unknown');
  const authorObj = typeof post.username === 'object' ? post.username : null;
  const authorAvatar = authorObj?.profile_image_url || post.author_avatar || getGravatarUrl(authorName);
  const authorLink = node.querySelector('.post-author');
  authorLink.textContent = authorName;
  authorLink.href = '#';
  const avatar = node.querySelector('.post-avatar');
  avatar.src = authorAvatar;
  avatar.alt = authorName;
  node.querySelector('.post-time').textContent = timeAgo(post.created_at);
  node.querySelector('.post-time').dateTime = post.created_at || '';
  node.querySelector('.post-body').textContent = post.caption || '';

  const likeButton = node.querySelector('.btn-reaction');
  const commentButton = node.querySelector('.btn-comment-toggle');
  const commentCount = commentButton.querySelector('.count');
  const commentCountValue = post.comments_count || 0;
  commentCount.textContent = commentCountValue;
  const isOwner = authorName === currentUser;

  // Comments section is hidden by default; click Comment to expand
  const commentsWrap = document.createElement('div');
  commentsWrap.className = 'post-comments-section';
  commentsWrap.style.display = 'none';
  const commentsEl = node.querySelector('.post-comments');
  const formComment = node.querySelector('.form-comment');
  formComment.style.display = 'none';
  commentsWrap.appendChild(commentsEl);
  commentsWrap.appendChild(formComment);
  node.appendChild(commentsWrap);

  // "View N comments" link under the post body when collapsed and there are comments
  let viewAllBtn = null;
  if (commentCountValue > 0) {
    viewAllBtn = document.createElement('button');
    viewAllBtn.className = 'load-comments-btn';
    viewAllBtn.textContent = `View all ${commentCountValue} comment${commentCountValue === 1 ? '' : 's'}`;
    viewAllBtn.addEventListener('click', () => expandComments());
    node.insertBefore(viewAllBtn, node.querySelector('.post-actions'));
  }
  let expanded = false;
  function expandComments() {
    expanded = true;
    commentsWrap.style.display = 'block';
    formComment.style.display = 'flex';
    if (viewAllBtn) viewAllBtn.remove();
    loadAllComments();
  }
  function collapseComments() {
    expanded = false;
    commentsWrap.style.display = 'none';
    formComment.style.display = 'none';
    if (commentCountValue > 0 && !viewAllBtn) {
      viewAllBtn = document.createElement('button');
      viewAllBtn.className = 'load-comments-btn';
      viewAllBtn.textContent = `View all ${commentCountValue} comment${commentCountValue === 1 ? '' : 's'}`;
      viewAllBtn.addEventListener('click', expandComments);
      node.insertBefore(viewAllBtn, node.querySelector('.post-actions'));
    }
  }

  let shownComments = 0;
  let allComments = [];
  let commentsLoaded = false;
  function renderCommentList() {
    commentsEl.innerHTML = '';
    allComments.slice(0, shownComments).forEach((c) => {
      commentsEl.appendChild(renderCommentNode(c, post));
    });
  }
  async function loadAllComments() {
    try {
      const data = await authFetch(ENDPOINTS.comment(post.id));
      const list = data.results || data || [];
      allComments = list;
      commentsLoaded = true;
      if (list.length > 3) {
        shownComments = 3;
        // Add a "show more" inside the list
        const showMore = document.createElement('button');
        showMore.className = 'load-comments-btn';
        showMore.textContent = `Show ${list.length - 3} more comments`;
        showMore.addEventListener('click', (e) => {
          e.preventDefault();
          shownComments = list.length;
          renderCommentList();
        });
        renderCommentList();
        commentsEl.appendChild(showMore);
      } else {
        shownComments = list.length;
        renderCommentList();
      }
      commentCount.textContent = list.length;
    } catch {}
  }

  // Toggle on Comment button click
  commentButton.addEventListener('click', (e) => {
    e.preventDefault();
    if (expanded) collapseComments();
    else expandComments();
  });

  // Reaction picker (long-press or hover)
  const picker = buildReactionPicker();
  likeButton.appendChild(picker);
  picker.addEventListener('click', async (e) => {
    const target = e.target.closest('.picker-emoji');
    if (!target) return;
    e.stopPropagation();
    const stickerName = target.dataset.sticker;
    const stickerId = stickerIdByName[stickerName];
    if (!stickerId) return;
    likeButton.disabled = true;
    try {
      const result = await authFetch(ENDPOINTS.like(post.id), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sticker_id: stickerId }),
      });
      applyReactionResult(post, result);
      updateLikeButton(likeButton, post);
      updateReactionSummary(node, post);
    } catch (err) {
      showToast(`Unable to react: ${err.message}`, 'error');
    } finally {
      likeButton.disabled = false;
      picker.classList.remove('open');
    }
  });
  likeButton.addEventListener('mouseenter', () => picker.classList.add('open'));
  likeButton.addEventListener('mouseleave', () => picker.classList.remove('open'));
  likeButton.addEventListener('click', async (e) => {
    if (e.target.closest('.picker-emoji')) return; // handled by picker
    if (picker.classList.contains('open')) {
      picker.classList.remove('open');
      e.preventDefault();
      likeButton.disabled = true;
      try {
        const result = await authFetch(ENDPOINTS.like(post.id), { method: 'POST' });
        applyReactionResult(post, result);
        updateLikeButton(likeButton, post);
        updateReactionSummary(node, post);
      } catch (err) {
        showToast(`Unable to like: ${err.message}`, 'error');
      } finally {
        likeButton.disabled = false;
      }
    } else {
      picker.classList.add('open');
      e.preventDefault();
    }
  });

  updateLikeButton(likeButton, post);
  updateReactionSummary(node, post);

  const imgWrap = node.querySelector('.post-image-wrap');
  if (post.image_url) {
    const img = document.createElement('img');
    img.src = post.image_url;
    img.alt = post.caption || 'Post image';
    img.loading = 'lazy';
    imgWrap.appendChild(img);
  } else {
    imgWrap.remove();
  }

  const videoWrap = node.querySelector('.post-video-wrap');
  if (post.video_url) {
    const video = document.createElement('video');
    video.src = post.video_url;
    video.controls = true;
    video.preload = 'metadata';
    videoWrap.appendChild(video);
  } else {
    videoWrap.remove();
  }

  // Comment form submit (re-uses the formComment declared above)
  formComment.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!expanded) expandComments();
    const input = node.querySelector('.input-comment');
    const value = input.value.trim();
    if (!value) return;
    const submitBtn = formComment.querySelector('.btn-small');
    submitBtn.disabled = true;
    try {
      const data = await authFetch(ENDPOINTS.comment(post.id), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: value }),
      });
      const commentData = data && (data.id ? data : (data.comment || data));
      const normalized = {
        id: commentData.id,
        content: commentData.content || value,
        author: commentData.author?.username || currentUser,
        author_avatar: authorAvatar,
        created_on: commentData.created_on || new Date().toISOString(),
        likes_count: 0, liked: false, reactions: [], replies: [], is_edited: false,
      };
      allComments = [normalized, ...allComments];
      shownComments = Math.max(shownComments, allComments.length);
      renderCommentList();
      input.value = '';
      commentCount.textContent = (Number(commentCount.textContent) || 0) + 1;
    } catch (err) {
      showToast(`Unable to add comment: ${err.message}`, 'error');
    } finally {
      submitBtn.disabled = false;
    }
  });

  const btnDelete = node.querySelector('.btn-delete');
  if (btnDelete) {
    if (!isOwner) {
      btnDelete.style.display = 'none';
    } else {
      btnDelete.addEventListener('click', async (e) => {
        e.preventDefault();
        if (!confirm('Delete this post?')) return;
        try {
          await authFetch(ENDPOINTS.delete(post.id), { method: 'POST' });
          node.style.transition = 'opacity 0.2s, transform 0.2s';
          node.style.opacity = '0';
          node.style.transform = 'scale(0.95)';
          setTimeout(() => node.remove(), 200);
          showToast('Post deleted', 'success');
        } catch (err) {
          showToast(`Unable to delete: ${err.message}`, 'error');
        }
      });
    }
  }

  const btnBookmark = node.querySelector('.btn-bookmark');
  let bookmarked = !!post.bookmarked;
  function updateBookmark() {
    btnBookmark.classList.toggle('active', bookmarked);
    const label = btnBookmark.querySelector('.label');
    if (label) label.textContent = bookmarked ? 'Saved' : 'Save';
  }
  updateBookmark();
  btnBookmark.addEventListener('click', async (e) => {
    e.preventDefault();
    try {
      if (bookmarked) {
        const list = await authFetch(ENDPOINTS.bookmarks);
        const items = list.results || list;
        const found = (items || []).find(b => (b.post?.id || b.post || b.id) === post.id);
        if (found) await authFetch(ENDPOINTS.bookmarkDelete(found.id), { method: 'DELETE' });
        bookmarked = false;
        showToast('Removed from bookmarks', 'success');
      } else {
        await authFetch(ENDPOINTS.bookmarkCreate, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ post: post.id }) });
        bookmarked = true;
        showToast('Saved to bookmarks', 'success');
      }
      updateBookmark();
    } catch (err) {
      showToast(`Unable to bookmark: ${err.message}`, 'error');
    }
  });

  const btnShare = node.querySelector('.btn-share');
  btnShare.addEventListener('click', async (e) => {
    e.preventDefault();
    const url = `${location.origin}/#post-${post.id}`;
    try {
      await navigator.clipboard.writeText(url);
      showToast('Link copied to clipboard', 'success');
    } catch {
      showToast(url, 'success');
    }
  });

  authorLink.addEventListener('click', async (e) => {
    e.preventDefault();
    try {
      const profile = await authFetch(ENDPOINTS.profile(authorName));
      const data = profile.user_profile || profile;
      showProfilePreview(data);
    } catch (err) {
      showToast(`Unable to load profile: ${err.message}`, 'error');
    }
  });

  return node;
}

function applyReactionResult(post, result) {
  if (!result) return;
  post.is_liked = !!result.user_sticker;
  post.user_sticker = result.user_sticker?.name || null;
  post.user_sticker_id = result.user_sticker?.sticker_id || null;
  post.total_reactions = result.total_reactions ?? result.total_count ?? post.total_reactions;
  post.reaction_counts = result.counts || post.reaction_counts || {};
  post.reactions = result.reactions || post.reactions || [];
}

function renderCommentNode(c, post) {
  const wrap = document.createElement('div');
  wrap.className = 'comment-thread';
  wrap.dataset.id = c.id;
  const item = document.createElement('div');
  item.className = 'comment-item';
  const av = document.createElement('img');
  av.className = 'avatar comment-avatar';
  av.src = c.author_avatar || (c.author?.profile_image_url) || getGravatarUrl(typeof c.author === 'string' ? c.author : (c.author?.username || ''));
  av.alt = typeof c.author === 'string' ? c.author : (c.author?.username || '');
  item.appendChild(av);

  const right = document.createElement('div');
  right.style.flex = '1';
  right.style.minWidth = '0';

  const bubble = document.createElement('div');
  bubble.className = 'comment-bubble';
  const authorName = typeof c.author === 'string' ? c.author : (c.author?.username || 'User');
  bubble.innerHTML = `<span class="comment-author">${escapeHtml(authorName)}</span><p class="comment-content"></p>`;
  const contentP = bubble.querySelector('.comment-content');
  contentP.textContent = c.content || '';
  if (c.is_edited) {
    const edited = document.createElement('span');
    edited.className = 'comment-edited';
    edited.textContent = ' · edited';
    contentP.appendChild(edited);
  }
  right.appendChild(bubble);

  const meta = document.createElement('div');
  meta.className = 'comment-meta';
  const time = document.createElement('time');
  time.textContent = timeAgo(c.created_on);
  meta.appendChild(time);

  const isOwner = authorName === currentUser;

  // Reaction button for comments (like post reactions)
  const reactionBtn = document.createElement('button');
  reactionBtn.className = 'btn-reaction btn-comment-reaction';
  const userStickerName = c.user_sticker || null;
  const isLiked = !!c.liked;
  reactionBtn.classList.toggle('liked', isLiked);
  reactionBtn.setAttribute('aria-pressed', isLiked ? 'true' : 'false');
  reactionBtn.dataset.sticker = userStickerName || '';
  const stickerEmoji = (STICKER_CATALOG.find((s) => s.name === userStickerName) || {}).emoji || '👍';
  reactionBtn.innerHTML = `<span class="icon">${stickerEmoji}</span> <span class="label">Like</span> <span class="count">${c.likes_count || 0}</span>`;

  const reactionPicker = buildReactionPicker();
  reactionBtn.appendChild(reactionPicker);
  meta.appendChild(reactionBtn);

  reactionPicker.addEventListener('click', async (e) => {
    const target = e.target.closest('.picker-emoji');
    if (!target) return;
    e.stopPropagation();
    const stickerName = target.dataset.sticker;
    const stickerId = stickerIdByName[stickerName];
    if (!stickerId) return;
    reactionBtn.disabled = true;
    try {
      const res = await authFetch(ENDPOINTS.commentSticker(c.id), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sticker_id: stickerId }),
      });
      const liked = !!res.liked;
      c.liked = liked;
      c.likes_count = res.likes_count || c.likes_count;
      c.user_sticker = liked ? stickerName : null;
      reactionBtn.classList.toggle('liked', liked);
      reactionBtn.setAttribute('aria-pressed', liked ? 'true' : 'false');
      reactionBtn.dataset.sticker = liked ? stickerName : '';
      const emoji = (STICKER_CATALOG.find((s) => s.name === stickerName) || {}).emoji || '👍';
      reactionBtn.querySelector('.icon').textContent = liked ? emoji : '👍';
      reactionBtn.querySelector('.count').textContent = c.likes_count;
      updateCommentReactionSummary(wrap, c);
    } catch (err) {
      showToast(`Unable to react: ${err.message}`, 'error');
    } finally {
      reactionBtn.disabled = false;
      reactionPicker.classList.remove('open');
    }
  });

  reactionBtn.addEventListener('click', async (e) => {
    if (e.target.closest('.picker-emoji')) return;
    if (reactionPicker.classList.contains('open')) {
      reactionPicker.classList.remove('open');
      e.preventDefault();
      reactionBtn.disabled = true;
      try {
        const res = await authFetch(ENDPOINTS.commentLike(c.id), { method: 'POST' });
        c.liked = !!res.liked;
        c.likes_count = res.likes_count;
        reactionBtn.classList.toggle('liked', c.liked);
        reactionBtn.setAttribute('aria-pressed', c.liked ? 'true' : 'false');
        reactionBtn.querySelector('.icon').textContent = c.liked ? '👍' : '👍';
        reactionBtn.querySelector('.count').textContent = c.likes_count;
        updateCommentReactionSummary(wrap, c);
      } catch (err) {
        showToast(`Unable to like: ${err.message}`, 'error');
      } finally {
        reactionBtn.disabled = false;
      }
    } else {
      reactionPicker.classList.add('open');
      e.preventDefault();
    }
  });
  reactionBtn.addEventListener('mouseenter', () => reactionPicker.classList.add('open'));
  reactionBtn.addEventListener('mouseleave', () => reactionPicker.classList.remove('open'));

  updateCommentReactionSummary(wrap, c);

  // Edit / Delete for owner
  if (authorName === currentUser) {
    const editBtn = document.createElement('button');
    editBtn.className = 'btn-link';
    editBtn.textContent = 'Edit';
    editBtn.addEventListener('click', () => {
      const existingForm = right.querySelector('.comment-edit-form');
      if (existingForm) { existingForm.remove(); return; }
      const form = document.createElement('form');
      form.className = 'comment-edit-form';
      form.innerHTML = `<input value=""><button class="btn-small" type="submit">Save</button>`;
      const input = form.querySelector('input');
      input.value = c.content;
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const newContent = input.value.trim();
        if (!newContent) return;
        try {
          const res = await authFetch(ENDPOINTS.commentDetail(c.id), {
            method: 'PATCH', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: newContent }),
          });
          c.content = res.content;
          c.is_edited = true;
          contentP.textContent = newContent;
          const ed = document.createElement('span');
          ed.className = 'comment-edited';
          ed.textContent = ' · edited';
          contentP.appendChild(ed);
          form.remove();
        } catch (err) {
          showToast(`Unable to edit: ${err.message}`, 'error');
        }
      });
      right.appendChild(form);
      input.focus();
    });
    meta.appendChild(editBtn);

    const delBtn = document.createElement('button');
    delBtn.className = 'btn-link danger';
    delBtn.textContent = 'Delete';
    delBtn.addEventListener('click', async () => {
      if (!confirm('Delete this comment?')) return;
      try {
        await authFetch(ENDPOINTS.commentDetail(c.id), { method: 'DELETE' });
        wrap.remove();
        // Update count in post card
        const postCard = post && post._node;
        if (postCard) {
          const cc = postCard.querySelector('.btn-comment-toggle .count');
          cc.textContent = Math.max(0, (Number(cc.textContent) || 1) - 1);
        }
      } catch (err) {
        showToast(`Unable to delete: ${err.message}`, 'error');
      }
    });
    meta.appendChild(delBtn);
  }

  right.appendChild(meta);

  // Reactions display
  if (c.reactions && c.reactions.length) {
    const reactionsEl = document.createElement('div');
    reactionsEl.className = 'comment-reactions';
    c.reactions.forEach((r) => {
      const span = document.createElement('span');
      span.className = 'reaction-emoji';
      span.textContent = `${r.emoji || ''} ${r.count || 0}`;
      reactionsEl.appendChild(span);
    });
    right.appendChild(reactionsEl);
  }

  item.appendChild(right);
  wrap.appendChild(item);

  // Replies
  const repliesEl = document.createElement('div');
  repliesEl.className = 'comment-replies';
  (c.replies || []).forEach((reply) => {
    const replyNode = renderCommentNode(reply, post);
    repliesEl.appendChild(replyNode);
  });
  function renderReplies() {
    repliesEl.innerHTML = '';
    (c.replies || []).forEach((reply) => {
      const replyNode = renderCommentNode(reply, post);
      repliesEl.appendChild(replyNode);
    });
  }
  wrap.appendChild(repliesEl);
  return wrap;
}

function buildReplyForm(parentComment, post, onCreated) {
  const form = document.createElement('form');
  form.className = 'comment-reply-form';
  form.innerHTML = `<input placeholder="Write a reply..."><button class="btn-small" type="submit">Reply</button>`;
  const input = form.querySelector('input');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    try {
      const res = await authFetch(ENDPOINTS.comment(post.id), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text, parent: parentComment.id }),
      });
      const c = res && (res.id ? res : (res.comment || res));
      onCreated({
        id: c.id, content: c.content || text,
        author: c.author?.username || currentUser,
        created_on: c.created_on || new Date().toISOString(),
        likes_count: 0, liked: false, reactions: [], replies: [], is_edited: false,
      });
      input.value = '';
      form.remove();
    } catch (err) {
      showToast(`Unable to reply: ${err.message}`, 'error');
    }
  });
  return form;
}

function updateCommentReactionSummary(wrap, c) {
  let summary = wrap.querySelector('.comment-reaction-summary');
  if (!summary) {
    summary = document.createElement('div');
    summary.className = 'comment-reaction-summary';
    wrap.appendChild(summary);
  }
  summary.innerHTML = '';
  const reactions = c.reactions || [];
  const counts = c.reaction_counts || {};
  if (!reactions.length && !Object.keys(counts).length) return;
  const top = reactions.slice().sort((a, b) => (counts[b.sticker_id] || b.count || 0) - (counts[a.sticker_id] || a.count || 0)).slice(0, 3);
  top.forEach((r) => {
    const span = document.createElement('span');
    span.className = 'reaction-emoji';
    span.textContent = r.emoji || '👍';
    summary.appendChild(span);
  });
  const total = document.createElement('span');
  total.textContent = `${c.likes_count || 0}`;
  summary.appendChild(total);
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

async function loadStickers() {
  try {
    const data = await authFetch(ENDPOINTS.stickers);
    const list = data.results || data || [];
    list.forEach((s) => {
      if (s.name) stickerIdByName[s.name] = s.id;
    });
  } catch (e) {
    // Fall back to fetching via get_or_create behavior (server side already creates defaults)
    stickerIdByName = {};
  }
}

function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  const colors = { success: 'var(--success)', error: 'var(--danger)', info: 'var(--accent)' };
  toast.style.cssText = `background:var(--card);color:var(--text);padding:12px 18px;border-radius:var(--radius-sm);box-shadow:var(--shadow-lg);border-left:4px solid ${colors[type] || colors.info};font-size:0.9rem;font-weight:500;max-width:340px;opacity:0;transform:translateY(10px);transition:all 0.3s ease;pointer-events:auto`;
  toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(() => { toast.style.opacity = '1'; toast.style.transform = 'translateY(0)'; });
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function showProfilePreview(profile) {
  const username = profile.username || '';
  const html = `
    <div style="text-align:center;padding:8px 0">
      <img class="avatar" src="${profile.profile_image_url || getGravatarUrl(profile.email)}" alt="" style="width:80px;height:80px;margin:0 auto 12px">
      <h3 style="margin:0 0 4px 0">${username || 'Unknown'}</h3>
      <p style="margin:0 0 12px 0;color:var(--text-secondary);font-size:0.9rem">${profile.email || ''}</p>
      <p style="margin:0;color:var(--text);font-size:0.9rem;line-height:1.5">${profile.bio || 'No bio yet.'}</p>
      <div style="display:flex;gap:8px;justify-content:center;margin-top:12px">
        <button id="profile-follow-btn" class="btn-primary">Follow</button>
        <button id="profile-message-btn" class="btn-primary">Message</button>
      </div>
    </div>
  `;
  showModal({ title: `Profile — ${username}`, content: html });

  // Attach actions
  const followBtn = document.getElementById('profile-follow-btn');
  const messageBtn = document.getElementById('profile-message-btn');
  if (followBtn) {
    followBtn.addEventListener('click', async (e) => {
      e.preventDefault(); followBtn.disabled = true;
      try {
        const res = await authFetch(ENDPOINTS.follow(username), { method: 'POST' });
        followBtn.textContent = res && res.is_following ? 'Following' : 'Follow';
        showToast(res && res.message ? res.message : 'Follow updated', 'success');
      } catch (err) {
        showToast(`Unable to follow: ${err.message}`, 'error');
      } finally { followBtn.disabled = false; }
    });
  }
  if (messageBtn) {
    messageBtn.addEventListener('click', (e) => {
      e.preventDefault();
      // navigate to messages page for a full experience
      goTo(`messages.html?user=${encodeURIComponent(username)}`);
    });
  }
}

let nextPage = null;
let loadingPosts = false;

function renderEmptyState(message) {
  return `<div class="empty-state"><div class="icon">📭</div><p>${message}</p></div>`;
}

async function fetchPosts(append = false) {
  if (loadingPosts) return;
  loadingPosts = true;
  const postsEl = document.getElementById('posts');
  if (!append && postsEl) postsEl.innerHTML = '<div class="spinner"></div>';
  try {
    const data = await authFetch(ENDPOINTS.index);
    if (!postsEl) return;
    if (!append) postsEl.innerHTML = '';
    const posts = data.results || data.posts || [];
    if (!posts.length && !append) {
      postsEl.innerHTML = renderEmptyState('Your feed is empty. Follow people or create your first post!');
    } else {
      posts.forEach((post, i) => {
        const el = renderPost(post);
        if (el) {
          el.style.animationDelay = `${Math.min(i * 50, 400)}ms`;
          postsEl.appendChild(el);
        }
      });
    }
    nextPage = data.next || null;
    const loadMoreBtn = document.getElementById('btn-load-more');
    if (loadMoreBtn) loadMoreBtn.disabled = !nextPage;
  } catch (err) {
    if (!append && postsEl) postsEl.innerHTML = renderEmptyState(`Unable to load feed: ${err.message}`);
  } finally {
    loadingPosts = false;
  }
}

async function loadMore() {
  if (!nextPage || loadingPosts) return;
  loadingPosts = true;
  try {
    const data = await authFetch(nextPage);
    const postsEl = document.getElementById('posts');
    if (!postsEl) return;
    const posts = data.results || data.posts || [];
    posts.forEach((post) => postsEl.appendChild(renderPost(post)));
    nextPage = data.next || null;
    const loadMoreBtn = document.getElementById('btn-load-more');
    if (loadMoreBtn) loadMoreBtn.disabled = !nextPage;
  } catch (err) {
    showToast(`Unable to load more: ${err.message}`, 'error');
  } finally {
    loadingPosts = false;
  }
}

async function handleCreatePost(e) {
  e.preventDefault();
  const form = e.target;
  const feedback = document.getElementById('post-feedback-modal');
  const submitBtn = document.getElementById('btn-submit-post');
  const caption = form.querySelector('#post-body-modal').value.trim();
  const fileInput = form.querySelector('#post-image-modal');
  const file = fileInput.files[0];

  if (!caption && !file) {
    setFeedback(feedback, 'Write something or attach a photo first.', true);
    return;
  }

  const fd = new FormData();
  fd.append('caption', caption);
  if (file) fd.append('media_upload', file);

  submitBtn.disabled = true;
  setFeedback(feedback, 'Posting…', false);
  try {
    const data = await authFetch(ENDPOINTS.upload, { method: 'POST', body: fd });
    setFeedback(feedback, 'Posted!', false);
    if (data) {
      const postsEl = document.getElementById('posts');
      const empty = postsEl.querySelector('.empty-state');
      if (empty) empty.remove();
      postsEl.prepend(renderPost(normalizePost(data)));
    }
    setTimeout(() => {
      form.reset();
      setFeedback(feedback, '', false);
      closeModal('create-post-modal');
    }, 600);
  } catch (err) {
    setFeedback(feedback, `Unable to post: ${err.message}`, true);
  } finally {
    submitBtn.disabled = false;
  }
}

function normalizePost(data) {
  if (data.post) return { ...data.post, ...normalizePost(data.post) };
  return data;
}

async function handleSignin(e) {
  e.preventDefault();
  const username = document.getElementById('signin-username').value.trim();
  const password = document.getElementById('signin-password').value;
  const feedback = document.getElementById('signin-feedback');
  const submitBtn = e.target.querySelector('button[type="submit"]');

  if (!username || !password) {
    setFeedback(feedback, 'Enter both username/email and password.', true);
    return;
  }

  submitBtn.disabled = true;
  setFeedback(feedback, 'Signing in…', false);
  try {
    const formBody = new URLSearchParams({ username, password });
    await apiRequest(ENDPOINTS.signin, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json' },
      body: formBody,
    });
    try {
      const tokenData = await apiRequest(ENDPOINTS.token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json' },
        body: formBody,
      });
      saveTokens(tokenData);
    } catch (_) {}
    goTo('index.html');
  } catch (err) {
    setFeedback(feedback, err.message, true);
  } finally {
    submitBtn.disabled = false;
  }
}

async function handleSignup(e) {
  e.preventDefault();
  const username = document.getElementById('signup-username').value.trim();
  const email = document.getElementById('signup-email').value.trim();
  const password = document.getElementById('signup-password').value;
  const feedback = document.getElementById('signup-feedback');
  const submitBtn = e.target.querySelector('button[type="submit"]');

  if (!username || !email || !password) {
    setFeedback(feedback, 'Fill in all fields.', true);
    return;
  }
  if (password.length < 8) {
    setFeedback(feedback, 'Password must be at least 8 characters.', true);
    return;
  }

  submitBtn.disabled = true;
  setFeedback(feedback, 'Creating account…', false);
  try {
    await apiRequest(ENDPOINTS.signup, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ username, email, password, confirm_password: password }),
    });

    const formBody = new URLSearchParams({ username, password });
    await apiRequest(ENDPOINTS.signin, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json' },
      body: formBody,
    });
    try {
      const tokenData = await apiRequest(ENDPOINTS.token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json' },
        body: formBody,
      });
      saveTokens(tokenData);
    } catch (_) {}

    goTo('index.html');
  } catch (err) {
    const msg = typeof err.data === 'object' ? Object.entries(err.data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join(' | ') : err.message;
    setFeedback(feedback, msg, true);
  } finally {
    submitBtn.disabled = false;
  }
}

function signOut() {
  clearTokens();
  goTo('signin.html');
}

async function loadProfileSummary() {
  const container = document.getElementById('profile-summary-content');
  if (!container) return;
  try {
    const data = await authFetch(ENDPOINTS.currentProfile);
    const profile = data || {};
    const username = profile.username || 'Unknown';
    const email = profile.email || '';
    const imageUrl = profile.profile_image_url || getGravatarUrl(email);
    setNavUser(username, email, imageUrl);
    container.innerHTML = `
      <div class="profile-card">
        <img class="avatar" src="${imageUrl}" alt="Profile photo of ${username}">
        <div class="meta">
          <strong>${username}</strong>
          <span>${email || 'No email'}</span>
          ${profile.bio ? `<small style="color:var(--text-secondary);font-size:0.8rem;display:block;margin-top:4px">${escapeHtml(profile.bio).slice(0, 80)}</small>` : ''}
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = renderEmptyState('Unable to load profile');
  }
}

async function showEditProfile() {
  const modal = document.getElementById('edit-profile-modal');
  if (!modal) return;
  try {
    const profile = await authFetch(ENDPOINTS.currentProfile);
    document.getElementById('edit-username').value = profile.username || '';
    document.getElementById('edit-email').value = profile.email || '';
    document.getElementById('edit-bio').value = profile.bio || '';
    const locEl = document.getElementById('edit-location');
    if (locEl) locEl.value = profile.location || '';
    const webEl = document.getElementById('edit-website');
    if (webEl) webEl.value = profile.website || '';
    const phoneEl = document.getElementById('edit-phone');
    if (phoneEl) phoneEl.value = profile.phone_number || '';
    const avatarPreview = document.getElementById('edit-avatar-preview');
    if (avatarPreview) {
      avatarPreview.src = profile.profile_image_url || getGravatarUrl(profile.email || '');
    }
    const fileInput = document.getElementById('edit-profile-pic');
    if (fileInput) {
      fileInput.value = '';
      fileInput.onchange = (e) => {
        const f = e.target.files[0];
        if (f && avatarPreview) avatarPreview.src = URL.createObjectURL(f);
      };
    }
    document.querySelectorAll('.edit-profile-tab').forEach((t, i) => t.classList.toggle('active', i === 0));
    document.querySelectorAll('.tabs-pane').forEach((p, i) => p.classList.toggle('active', i === 0));
    openModal('edit-profile-modal');
  } catch (err) {
    showToast(`Unable to load profile: ${err.message}`, 'error');
  }
}

async function handleEditProfile(e) {
  e.preventDefault();
  const form = e.target;
  const feedback = document.getElementById('edit-profile-feedback');
  const email = document.getElementById('edit-email').value.trim();
  const bio = document.getElementById('edit-bio').value.trim();
  const fileInput = document.getElementById('edit-profile-pic');
  const file = fileInput.files[0];
  const submitBtn = form.querySelector('button[type="submit"]');
  submitBtn.disabled = true;

  try {
    const fd = new FormData();
    fd.append('email', email);
    if (bio) fd.append('bio', bio);
    // backend expects `profile_image` field name
    if (file) fd.append('profile_image', file);

    const result = await authFetch(ENDPOINTS.settings, { method: 'POST', body: fd });
    setFeedback(feedback, 'Profile updated!', false);

    const imageUrl = result.user_profile?.profile_image_url || getGravatarUrl(email);
    setNavUser(currentUser, email, imageUrl);
    currentEmail = email;

    setTimeout(() => {
      setFeedback(feedback, '', false);
      closeModal('edit-profile-modal');
      loadProfileSummary();
    }, 800);
  } catch (err) {
    setFeedback(feedback, `Unable to update: ${err.message}`, true);
  } finally {
    submitBtn.disabled = false;
  }
}

async function loadMyPosts() {
  const list = document.getElementById('my-posts-list');
  if (!list) return;
  list.innerHTML = '<div class="spinner"></div>';
  openModal('my-posts-modal');
  try {
    // The feed already includes the current user's own posts
    const data = await authFetch(ENDPOINTS.index);
    const allPosts = data.results || data.posts || [];
    const myPosts = allPosts.filter(post => {
      const author = typeof post.username === 'object' ? post.username.username : post.username;
      return author === currentUser;
    });
    if (!myPosts.length) {
      list.innerHTML = renderEmptyState("You haven't posted anything yet");
      return;
    }
    list.innerHTML = '';
    myPosts.forEach(post => list.appendChild(renderPost(post)));
  } catch (err) {
    list.innerHTML = renderEmptyState(`Unable to load: ${err.message}`);
  }
}

function openModal(id) {
  const modal = document.getElementById(id);
  const overlay = document.getElementById('profile-modal-overlay');
  if (modal) modal.classList.add('open');
  if (overlay) overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal(id) {
  const modal = id ? document.getElementById(id) : null;
  const overlay = document.getElementById('profile-modal-overlay');
  if (modal) modal.classList.remove('open');
  const anyOpen = document.querySelector('.profile-modal.open, .posts-modal.open, .edit-profile-modal.open');
  if (!anyOpen) {
    if (overlay) overlay.classList.remove('open');
    document.body.style.overflow = '';
  }
  const picBtn = document.getElementById('profile-pic-btn');
  if (picBtn && !anyOpen) picBtn.setAttribute('aria-expanded', 'false');
}

function showModal({ title, content }) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.style.zIndex = '200';
  const modal = document.createElement('div');
  modal.className = 'profile-modal open';
  modal.style.zIndex = '201';
  modal.innerHTML = `
    <div class="modal-content">
      <button class="btn-close" aria-label="Close">×</button>
      <h2>${title}</h2>
      ${content}
    </div>
  `;
  document.body.appendChild(overlay);
  document.body.appendChild(modal);
  document.body.style.overflow = 'hidden';
  const close = () => {
    overlay.remove();
    modal.remove();
    document.body.style.overflow = '';
  };
  modal.querySelector('.btn-close').addEventListener('click', close);
  overlay.addEventListener('click', close);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.querySelector('.theme-icon');
  if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
  try { localStorage.setItem('theme', theme); } catch {}
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  applyTheme(current === 'dark' ? 'light' : 'dark');
}

async function init() {
  const path = location.pathname.split('/').pop();

  try {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) applyTheme(savedTheme);
  } catch {}

  if (path === 'signin.html') {
    if (readAccessToken()) { goTo('index.html'); return; }
    const form = document.getElementById('form-signin');
    if (form) form.addEventListener('submit', handleSignin);
    return;
  }

  if (path === 'signup.html') {
    if (readAccessToken()) { goTo('index.html'); return; }
    const form = document.getElementById('form-signup');
    if (form) form.addEventListener('submit', handleSignup);
    return;
  }

  // If no JWT token, try session-based auth before redirecting to signin
  if (!readAccessToken()) {
    try {
      await authFetch(ENDPOINTS.index);
    } catch (e) {
      goTo('signin.html');
      return;
    }
  }

  // If we're on the messages page, render the full conversation
  if (path === 'messages.html') {
    const params = new URLSearchParams(location.search);
    const user = params.get('user');
    await initMessagesPage(user);
    return;
  }

  const formPostModal = document.getElementById('form-post-modal');
  if (formPostModal) formPostModal.addEventListener('submit', handleCreatePost);

  const loadMoreBtn = document.getElementById('btn-load-more');
  if (loadMoreBtn) loadMoreBtn.addEventListener('click', loadMore);

  const profilePicBtn = document.getElementById('profile-pic-btn');
  const profileModal = document.getElementById('profile-modal');
  const modalOverlay = document.getElementById('profile-modal-overlay');

  if (profilePicBtn && profileModal) {
    profilePicBtn.addEventListener('click', () => {
      const isOpen = profileModal.classList.contains('open');
      if (isOpen) closeModal('profile-modal');
      else {
        profileModal.classList.add('open');
        if (modalOverlay) modalOverlay.classList.add('open');
        document.body.style.overflow = 'hidden';
        profilePicBtn.setAttribute('aria-expanded', 'true');
      }
    });
  }

  if (modalOverlay) {
    modalOverlay.addEventListener('click', () => {
      document.querySelectorAll('.profile-modal.open, .posts-modal.open, .edit-profile-modal.open').forEach(m => m.classList.remove('open'));
      modalOverlay.classList.remove('open');
      document.body.style.overflow = '';
      if (profilePicBtn) profilePicBtn.setAttribute('aria-expanded', 'false');
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.profile-modal.open, .posts-modal.open, .edit-profile-modal.open').forEach(m => m.classList.remove('open'));
      if (modalOverlay) modalOverlay.classList.remove('open');
      document.body.style.overflow = '';
    }
  });

  document.querySelectorAll('[id^="btn-close-"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const modal = btn.closest('.profile-modal, .posts-modal, .edit-profile-modal');
      if (modal) closeModal(modal.id);
    });
  });

  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);
  const themeModalBtn = document.getElementById('btn-theme-modal');
  if (themeModalBtn) themeModalBtn.addEventListener('click', () => { toggleTheme(); closeModal('profile-modal'); });

  const signOutBtn = document.getElementById('btn-signout-modal');
  if (signOutBtn) signOutBtn.addEventListener('click', () => { signOut(); closeModal('profile-modal'); });

  const createPostBtn = document.getElementById('btn-create-post-modal');
  if (createPostBtn) createPostBtn.addEventListener('click', () => { closeModal('profile-modal'); openModal('create-post-modal'); });
  const createPostTrigger = document.getElementById('create-post-trigger');
  if (createPostTrigger) createPostTrigger.addEventListener('click', () => openModal('create-post-modal'));
  document.querySelectorAll('.create-post-action[data-media]').forEach(btn => {
    btn.addEventListener('click', () => {
      openModal('create-post-modal');
      const fileInput = document.getElementById('post-image-modal');
      if (fileInput) {
        fileInput.accept = btn.dataset.media === 'video' ? 'video/*' : 'image/*';
        fileInput.click();
      }
    });
  });

  const myPostsBtn = document.getElementById('btn-my-posts-modal');
  if (myPostsBtn) myPostsBtn.addEventListener('click', () => { closeModal('profile-modal'); loadMyPosts(); });
  const editProfileBtn = document.getElementById('btn-edit-profile-modal');
  if (editProfileBtn) editProfileBtn.addEventListener('click', () => { closeModal('profile-modal'); showEditProfile(); });
  const editProfileForm = document.getElementById('form-edit-profile');
  if (editProfileForm) editProfileForm.addEventListener('submit', handleEditProfile);
  const passwordForm = document.getElementById('form-change-password');
  if (passwordForm) passwordForm.addEventListener('submit', handleChangePassword);
  document.querySelectorAll('.edit-profile-tab').forEach((tab) => {
    tab.addEventListener('click', (e) => {
      e.preventDefault();
      const target = tab.dataset.tab;
      document.querySelectorAll('.edit-profile-tab').forEach((t) => t.classList.toggle('active', t === tab));
      document.querySelectorAll('.tabs-pane').forEach((p) => p.classList.toggle('active', p.dataset.pane === target));
    });
  });

  const btnBookmarks = document.getElementById('btn-bookmarks-modal');
  if (btnBookmarks) btnBookmarks.addEventListener('click', () => { closeModal('profile-modal'); loadBookmarks(); });
  const btnNotifications = document.getElementById('btn-notifications-modal');
  if (btnNotifications) btnNotifications.addEventListener('click', () => { closeModal('profile-modal'); loadNotifications(); });
  const notifBtn = document.getElementById('notifications-btn');
  if (notifBtn) notifBtn.addEventListener('click', () => { loadNotifications(); openModal('notifications-modal'); });

  const navSearch = document.getElementById('nav-search');
  if (navSearch) navSearch.addEventListener('click', (e) => { e.preventDefault(); showSearchModal(); });
  const navMessages = document.getElementById('nav-messages');
  if (navMessages) navMessages.addEventListener('click', (e) => { e.preventDefault(); goTo('messages.html'); });
  const navNotifications = document.getElementById('nav-notifications');
  if (navNotifications) navNotifications.addEventListener('click', (e) => { e.preventDefault(); loadNotifications(); openModal('notifications-modal'); });
  const navBookmarks = document.getElementById('nav-bookmarks');
  if (navBookmarks) navBookmarks.addEventListener('click', (e) => { e.preventDefault(); loadBookmarks(); openModal('bookmarks-modal'); });
  const navProfile = document.getElementById('nav-profile');
  if (navProfile) navProfile.addEventListener('click', (e) => { e.preventDefault(); showEditProfile(); });

  loadTrending();
  loadSuggested();
  loadStories();
  loadUnreadCounts();
  startUnreadPolling();
  loadStickers();

  loadProfileSummary().then(fetchPosts).catch(() => fetchPosts());
}

function showSearchModal() {
  const content = `
    <form id="search-form">
      <div class="form-group">
        <input type="search" id="search-input" placeholder="Search people by username or email…" autocomplete="off">
      </div>
    </form>
    <div id="search-results" style="margin-top:12px"></div>
  `;
  showModal({ title: 'Search', content });
  const form = document.getElementById('search-form');
  const input = document.getElementById('search-input');
  const results = document.getElementById('search-results');
  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const q = input.value.trim();
      if (!q) { results.innerHTML = ''; return; }
      try {
        const data = await authFetch(`${ENDPOINTS.search}?q=${encodeURIComponent(q)}`);
        const users = data.results || data || [];
        if (!users.length) { results.innerHTML = '<p style="color:var(--muted);font-size:0.9rem">No users found.</p>'; return; }
        results.innerHTML = users.map(u => `
          <div class="suggested-item" data-username="${u.username}">
            <img class="avatar" src="${u.profile_image_url || getGravatarUrl(u.email, 40)}" alt="">
            <div class="meta">
              <strong class="suggested-username">${u.username}</strong>
              <span>${u.bio || u.email || ''}</span>
            </div>
            <div class="actions">
              <button class="btn-link btn-follow" data-username="${u.username}">Follow</button>
              <button class="btn-link btn-message" data-username="${u.username}">Message</button>
            </div>
          </div>
        `).join('');
        // Delegate clicks for the results: view profile when clicking the meta/avatar
        results.querySelectorAll('.suggested-item').forEach(item => {
          item.addEventListener('click', async (ev) => {
            const target = ev.target;
            const username = item.dataset.username;
            // If clicked a button, let its handler run instead
            if (target.closest('.actions')) return;
            ev.preventDefault();
            try {
              const profile = await authFetch(ENDPOINTS.profile(username));
              const data = profile.user_profile || profile;
              showProfilePreview(data);
            } catch (err) {
              showToast(`Unable to load profile: ${err.message}`, 'error');
            }
          });
        });
        // Attach follow/message handlers
        results.querySelectorAll('.btn-follow').forEach(btn => {
          btn.addEventListener('click', async (ev) => {
            ev.preventDefault(); ev.stopPropagation();
            const username = btn.dataset.username;
            btn.disabled = true;
            try {
              const res = await authFetch(ENDPOINTS.follow(username), { method: 'POST' });
              btn.textContent = res && res.is_following ? 'Following' : 'Follow';
              showToast(res && res.message ? res.message : 'Follow updated', 'success');
            } catch (err) {
              showToast(`Unable to follow: ${err.message}`, 'error');
            } finally { btn.disabled = false; }
          });
        });
        results.querySelectorAll('.btn-message').forEach(btn => {
          btn.addEventListener('click', (ev) => {
            ev.preventDefault(); ev.stopPropagation();
            const username = btn.dataset.username;
            // navigate to messages page for a full conversation view
            goTo(`messages.html?user=${encodeURIComponent(username)}`);
          });
        });
      } catch (err) {
        results.innerHTML = `<p style="color:var(--danger)">${err.message}</p>`;
      }
    }, 300);
  });
  setTimeout(() => input.focus(), 50);
}

async function loadUnreadCounts() {
  try {
    const [notifData, msgData] = await Promise.all([
      authFetch(ENDPOINTS.notificationsUnread).catch(() => null),
      authFetch(ENDPOINTS.messagesUnread).catch(() => null),
    ]);
    const notifBadge = document.getElementById('notifications-badge');
    if (notifBadge && notifData) {
      const c = notifData.unread_notifications_count || 0;
      notifBadge.textContent = c;
      notifBadge.style.display = c > 0 ? 'flex' : 'none';
    }
    const msgBadge = document.getElementById('messages-badge');
    if (msgBadge && msgData) {
      const c = msgData.unread_messages_count || 0;
      msgBadge.textContent = c;
      msgBadge.style.display = c > 0 ? 'flex' : 'none';
    }
  } catch {}
}

// Poll unread counts every 20s on the feed page
function startUnreadPolling() {
  if (window.__unreadPoll) return;
  window.__unreadPoll = setInterval(loadUnreadCounts, 20000);
}

async function loadTrending() {
  const list = document.getElementById('trending-list');
  if (!list) return;
  try {
    const data = await authFetch(ENDPOINTS.trending);
    const items = data.results || data || [];
    if (!items.length) {
      list.innerHTML = renderEmptyState('No trending topics yet');
      return;
    }
    list.innerHTML = items.slice(0, 8).map(item => `
      <div class="trending-item">
        <span>#${item.name}</span>
        <span class="score">${item.trending_score || 0}</span>
      </div>
    `).join('');
  } catch {
    list.innerHTML = '';
  }
}

async function loadSuggested() {
  const list = document.getElementById('suggestions-bar');
  if (!list) return;
  try {
    const data = await authFetch(ENDPOINTS.suggested);
    const users = data.results || data || [];
    if (!users.length) {
      list.innerHTML = '';
      return;
    }
    list.innerHTML = users.slice(0, 8).map(u => `
      <div class="suggestion-card" data-username="${u.username}">
        <img class="avatar" src="${u.profile_image_url || getGravatarUrl(u.email || u.username, 52)}" alt="${u.username}">
        <div class="suggestion-info">
          <strong>${u.username}</strong>
          <span>${u.bio ? u.bio.slice(0, 40) : (u.email || '')}</span>
        </div>
        <div class="suggestion-actions">
          <button class="btn-small btn-follow-suggestion" data-username="${u.username}">Follow</button>
          <button class="btn-link btn-message-suggestion" data-username="${u.username}">Message</button>
        </div>
      </div>
    `).join('');

    list.querySelectorAll('.suggestion-card').forEach(card => {
      card.addEventListener('click', async (e) => {
        const username = card.dataset.username;
        if (!username) return;
        try {
          const profile = await authFetch(ENDPOINTS.profile(username));
          showProfilePreview(profile.user_profile || profile);
        } catch (err) {
          showToast(`Unable to load profile: ${err.message}`, 'error');
        }
      });
    });

    list.querySelectorAll('.btn-follow-suggestion').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const username = btn.dataset.username;
        btn.disabled = true;
        try {
          const res = await authFetch(ENDPOINTS.follow(username), { method: 'POST' });
          btn.textContent = res && res.is_following ? 'Following' : 'Follow';
          showToast(res && res.message ? res.message : 'Follow updated', 'success');
        } catch (err) {
          showToast(`Unable to follow: ${err.message}`, 'error');
        } finally {
          btn.disabled = false;
        }
      });
    });

    list.querySelectorAll('.btn-message-suggestion').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const username = btn.dataset.username;
        goTo(`messages.html?user=${encodeURIComponent(username)}`);
      });
    });
  } catch {
    list.innerHTML = '';
  }
}

async function loadStories() {
  const bar = document.getElementById('stories-bar');
  if (!bar) return;
  try {
    const data = await authFetch(ENDPOINTS.index);
    const posts = data.results || data.posts || [];
    const seen = new Set();
    const users = [];
    posts.forEach(p => {
      const author = typeof p.username === 'object' ? p.username.username : p.username;
      if (author && !seen.has(author)) {
        seen.add(author);
        users.push({ username: author, image_url: p.image_url });
      }
    });
    if (!users.length) {
      bar.innerHTML = '';
      return;
    }
    const tpl = document.getElementById('tpl-story');
    bar.innerHTML = '';
    users.slice(0, 12).forEach(u => {
      const node = tpl.content.firstElementChild.cloneNode(true);
      node.querySelector('.story-avatar').src = u.image_url || getGravatarUrl(u.username, 60);
      node.querySelector('.story-username').textContent = u.username;
      node.addEventListener('click', async () => {
        try {
          const profile = await authFetch(ENDPOINTS.profile(u.username));
          showProfilePreview(profile.user_profile || profile);
        } catch {}
      });
      bar.appendChild(node);
    });
  } catch {
    bar.innerHTML = '';
  }
}

async function loadNotifications() {
  const list = document.getElementById('notifications-list');
  if (!list) return;
  list.innerHTML = '<div class="spinner"></div>';
  openModal('notifications-modal');
  try {
    const data = await authFetch(ENDPOINTS.notifications);
    const items = data.results || data || [];
    if (!items.length) {
      list.innerHTML = renderEmptyState('No notifications yet');
      return;
    }
    list.innerHTML = items.map(n => {
      const sender = n.sender?.username || 'System';
      const when = timeAgo(n.created_at);
      return `
        <div class="comment-item">
          <img class="avatar comment-avatar" src="${getGravatarUrl(sender)}" alt="">
          <div style="flex:1;min-width:0">
            <div class="comment-bubble">
              <span class="comment-author">${sender}</span>
              <p class="comment-content">${n.text || n.notification_type}</p>
            </div>
            <div class="comment-meta"><time>${when}</time></div>
          </div>
        </div>
      `;
    }).join('');
  } catch {
    list.innerHTML = renderEmptyState('Unable to load notifications');
  }
}

async function loadBookmarks() {
  const list = document.getElementById('bookmarks-list');
  if (!list) return;
  list.innerHTML = '<div class="spinner"></div>';
  openModal('bookmarks-modal');
  try {
    const data = await authFetch(ENDPOINTS.bookmarks);
    const items = data.results || data || [];
    if (!items.length) {
      list.innerHTML = renderEmptyState('No bookmarks yet');
      return;
    }
    list.innerHTML = '';
    items.forEach(b => {
      const post = b.post || b;
      const el = renderPost({
        id: post.id,
        username: post.username?.username || post.username,
        caption: post.caption,
        created_at: post.created_at,
        image_url: post.image_url,
        video_url: post.video_url,
        total_reactions: post.total_reactions || 0,
        is_liked: post.is_liked || false,
        user_sticker: post.user_sticker,
        user_sticker_id: post.user_sticker_id,
        reaction_counts: post.reaction_counts || {},
        reactions: post.reactions || [],
        comments_count: post.comments_count || 0,
        bookmarked: true,
      });
      if (el) list.appendChild(el);
    });
  } catch {
    list.innerHTML = renderEmptyState('Unable to load bookmarks');
  }
}

/* =================== MESSAGES PAGE =================== */
async function initMessagesPage(initialUser = null) {
  const root = document.getElementById('messages-root');
  if (!root) return;
  root.innerHTML = `
    <div class="messages-page-layout">
      <aside class="conversations-list" id="conversations-list">
        <div class="conversations-header">
          <span>Messages</span>
          <button class="btn-link" id="new-message-btn" title="Start new conversation" style="float:right">✏️</button>
        </div>
        <div id="conversations-items"></div>
      </aside>
      <section class="chat-container" id="chat-container">
        <div class="chat-empty" id="chat-empty">
          <div class="icon">💬</div>
          <p>Select a conversation to start chatting</p>
          <small>Or start a new one with the ✏️ button above.</small>
        </div>
      </section>
    </div>
  `;
  const newBtn = document.getElementById('new-message-btn');
  if (newBtn) newBtn.addEventListener('click', () => showNewConversationDialog());
  await loadConversations();
  if (initialUser) {
    selectConversation(initialUser);
  }
  // Poll for new conversations every 10s
  setInterval(loadConversations, 10000);
}

function showNewConversationDialog() {
  const content = `
    <form id="new-conv-form">
      <div class="form-group">
        <label>Username</label>
        <input type="text" id="new-conv-username" placeholder="Who do you want to message?" autocomplete="off" required>
      </div>
      <div class="form-row">
        <button type="submit" class="btn-primary">Start chat</button>
        <div id="new-conv-feedback" class="feedback"></div>
      </div>
    </form>
  `;
  showModal({ title: 'New conversation', content });
  const form = document.getElementById('new-conv-form');
  const input = document.getElementById('new-conv-username');
  const feedback = document.getElementById('new-conv-feedback');
  setTimeout(() => input.focus(), 50);
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = input.value.trim();
    if (!username) return;
    setFeedback(feedback, 'Opening chat…', false);
    try {
      // Verify user exists
      await authFetch(ENDPOINTS.profile(username));
      // Close the modal
      const modal = document.querySelector('.profile-modal.open');
      const overlay = document.querySelector('.modal-overlay.open');
      if (modal) modal.remove();
      if (overlay) overlay.remove();
      document.body.style.overflow = '';
      selectConversation(username);
    } catch (err) {
      setFeedback(feedback, `Unable to find user: ${err.message}`, true);
    }
  });
}

async function loadConversations() {
  const items = document.getElementById('conversations-items');
  if (!items) return;
  try {
    const data = await authFetch(ENDPOINTS.conversationList);
    const convs = data.conversations || data.results || data || [];
    if (!convs.length) {
      items.innerHTML = `<div class="chat-empty" style="padding:32px 16px"><div class="icon">📭</div><p>No conversations yet</p><small>Find people in search to start chatting.</small></div>`;
      return;
    }
    items.innerHTML = '';
    convs.forEach((c) => {
      const other = c.other_user || {};
      const last = c.last_message || {};
      const lastText = last.body || (last.image_url ? '📷 Image' : '—');
      const item = document.createElement('div');
      item.className = 'conversation-item';
      item.dataset.username = other.username;
      const avatarUrl = other.profile_image_url || getGravatarUrl(other.email || other.username, 44);
      item.innerHTML = `
        <img class="avatar" src="${avatarUrl}" alt="${other.username}">
        <div class="conversation-info">
          <div class="conversation-name">${escapeHtml(other.username || 'Unknown')}</div>
          <div class="conversation-preview">${escapeHtml(lastText).slice(0, 60)}</div>
        </div>
        <div class="conversation-meta">
          <span class="conversation-time">${last.created_at ? timeAgo(last.created_at) : ''}</span>
          ${c.unread_count ? `<span class="conversation-unread">${c.unread_count}</span>` : ''}
        </div>
      `;
      item.addEventListener('click', () => selectConversation(other.username));
      items.appendChild(item);
    });
  } catch (err) {
    items.innerHTML = `<p style="padding:16px;color:var(--danger)">${err.message}</p>`;
  }
}

let activeChat = null;

async function selectConversation(username) {
  document.querySelectorAll('.conversation-item').forEach((el) => el.classList.toggle('active', el.dataset.username === username));
  if (activeChat && activeChat.username === username) return;
  if (activeChat && activeChat.pollId) clearInterval(activeChat.pollId);
  if (activeChat && activeChat.scrollContainer) {
    try { activeChat.scrollContainer.removeEventListener('scroll', activeChat.onScroll); } catch {}
  }

  const chat = document.getElementById('chat-container');
  if (!chat) return;
  chat.innerHTML = `
    <div class="chat-header">
      <a href="#" class="btn-link" id="chat-back" style="display:none">←</a>
      <img class="avatar" id="chat-header-avatar" src="" alt="">
      <div class="chat-header-info">
        <div class="chat-header-name" id="chat-header-name">${escapeHtml(username)}</div>
        <div class="chat-typing" id="chat-typing"></div>
      </div>
    </div>
    <div class="chat-messages" id="chat-messages"></div>
    <form class="chat-input-form" id="chat-form">
      <button type="button" class="btn-attach" id="chat-attach" title="Attach image">📎</button>
      <input type="file" id="chat-image" accept="image/*" style="display:none">
      <textarea id="chat-input" rows="1" placeholder="Type a message..."></textarea>
      <button type="submit" class="btn-send" id="chat-send" title="Send">➤</button>
    </form>
  `;
  document.getElementById('chat-back').onclick = (e) => { e.preventDefault(); document.querySelector('.conversations-list').classList.remove('hidden'); chat.classList.add('hidden'); };

  // Header avatar
  try {
    const profile = await authFetch(ENDPOINTS.profile(username));
    const data = profile.user_profile || profile;
    document.getElementById('chat-header-avatar').src = data.profile_image_url || getGravatarUrl(data.email || username, 40);
  } catch {
    document.getElementById('chat-header-avatar').src = getGravatarUrl(username, 40);
  }

  activeChat = { username, messages: new Map(), nextUrl: null, pollId: null, scrollContainer: null, onScroll: null };

  const messagesEl = document.getElementById('chat-messages');
  const scrollContainer = messagesEl;
  activeChat.scrollContainer = scrollContainer;
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send');
  const attachBtn = document.getElementById('chat-attach');
  const imageInput = document.getElementById('chat-image');
  let pendingImage = null;

  // Auto-grow textarea
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 100) + 'px';
  });
  // Typing indicator (best-effort ping)
  let typingTimer = null;
  input.addEventListener('input', () => {
    if (typingTimer) return;
    authFetch(ENDPOINTS.conversationTyping(username), { method: 'POST' }).catch(() => {});
    typingTimer = setTimeout(() => { typingTimer = null; }, 2000);
  });

  attachBtn.addEventListener('click', () => imageInput.click());
  imageInput.addEventListener('change', (e) => {
    const f = e.target.files[0];
    if (f) {
      pendingImage = f;
      showToast('Image attached. Press send to upload.', 'info');
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = input.value.trim();
    if (!body && !pendingImage) return;
    sendBtn.disabled = true;
    try {
      const fd = new FormData();
      if (body) fd.append('body', body);
      if (pendingImage) fd.append('image', pendingImage);
      const res = await authFetch(ENDPOINTS.conversationSend(username), { method: 'POST', body: fd });
      const m = res.new_message;
      if (m) {
        activeChat.messages.set(m.id, m);
        renderMessage(m, true);
        scrollToBottom();
      }
      input.value = '';
      input.style.height = 'auto';
      pendingImage = null;
      imageInput.value = '';
    } catch (err) {
      showToast(`Unable to send: ${err.message}`, 'error');
    } finally {
      sendBtn.disabled = false;
    }
  });

  function renderMessage(m, prepend = false) {
    const isMe = m.is_mine || (m.sender?.username === currentUser) || (typeof m.sender === 'string' && m.sender === currentUser);
    const row = document.createElement('div');
    row.className = `chat-row ${isMe ? 'me' : 'them'}`;
    row.dataset.id = m.id;
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    if (m.is_deleted_by_sender && isMe) bubble.classList.add('deleted');
    if (m.body) {
      const text = document.createElement('div');
      text.className = 'chat-text';
      text.textContent = m.body;
      bubble.appendChild(text);
    }
    if (m.image_url) {
      const img = document.createElement('img');
      img.className = 'chat-image';
      img.src = m.image_url;
      img.alt = 'attachment';
      bubble.appendChild(img);
    }
    const meta = document.createElement('div');
    meta.className = 'chat-meta';
    const time = document.createElement('span');
    time.textContent = timeAgo(m.created_at);
    meta.appendChild(time);
    if (m.is_edited) {
      const ed = document.createElement('span');
      ed.textContent = 'edited';
      meta.appendChild(ed);
    }
    if (isMe) {
      const tick = document.createElement('span');
      tick.className = 'read-tick ' + (m.is_read || m.seen_at ? 'read' : '');
      tick.textContent = m.is_read || m.seen_at ? '✓✓' : '✓';
      meta.appendChild(tick);
    }
    bubble.appendChild(meta);

    if (isMe && !m.is_deleted_by_sender) {
      const actions = document.createElement('div');
      actions.className = 'chat-bubble-actions';
      const editBtn = document.createElement('button');
      editBtn.title = 'Edit';
      editBtn.textContent = '✏️';
      editBtn.addEventListener('click', () => editMessage(m, bubble));
      const delBtn = document.createElement('button');
      delBtn.title = 'Delete';
      delBtn.textContent = '🗑';
      delBtn.addEventListener('click', () => deleteMessage(m, row));
      actions.appendChild(editBtn);
      actions.appendChild(delBtn);
      bubble.appendChild(actions);
    }
    row.appendChild(bubble);
    if (prepend) {
      messagesEl.insertBefore(row, messagesEl.firstChild);
    } else {
      messagesEl.appendChild(row);
    }
  }

  function scrollToBottom() {
    scrollContainer.scrollTop = scrollContainer.scrollHeight;
  }

  async function loadInitial() {
    messagesEl.innerHTML = '<div class="spinner" style="margin:auto"></div>';
    try {
      const data = await authFetch(ENDPOINTS.conversation(username));
      const list = data.results || data.conversation || data || [];
      const ordered = list.slice().reverse();
      messagesEl.innerHTML = '';
      ordered.forEach((m) => {
        activeChat.messages.set(m.id, m);
        renderMessage(m);
      });
      scrollToBottom();
      activeChat.nextUrl = data.next || null;
      // mark as read
      authFetch(ENDPOINTS.conversationRead(username), { method: 'POST' }).catch(() => {});
      loadConversations(); // refresh unread badges
    } catch (err) {
      messagesEl.innerHTML = `<div style="color:var(--danger);padding:16px">${err.message}</div>`;
    }
  }

  // Poll for new messages
  activeChat.pollId = setInterval(async () => {
    try {
      const data = await authFetch(ENDPOINTS.conversation(username));
      const list = data.results || data.conversation || data || [];
      const ordered = list.slice().reverse();
      let appended = 0;
      ordered.forEach((m) => {
        if (!activeChat.messages.has(m.id)) {
          activeChat.messages.set(m.id, m);
          renderMessage(m);
          appended++;
        } else if (m.is_edited || m.is_read) {
          // update existing bubble meta
          const row = messagesEl.querySelector(`[data-id="${m.id}"] .chat-bubble`);
          if (row) {
            const existing = activeChat.messages.get(m.id);
            existing.is_read = m.is_read;
            existing.is_edited = m.is_edited;
            existing.body = m.body;
            const text = row.querySelector('.chat-text');
            if (text && m.body) text.textContent = m.body;
          }
        }
      });
      if (appended) {
        scrollToBottom();
        authFetch(ENDPOINTS.conversationRead(username), { method: 'POST' }).catch(() => {});
      }
    } catch {}
  }, 4000);

  // Load earlier on scroll-up
  activeChat.onScroll = async () => {
    if (!activeChat.nextUrl || scrollContainer.scrollTop > 60) return;
    const prevHeight = scrollContainer.scrollHeight;
    try {
      const data = await authFetch(activeChat.nextUrl);
      const list = data.results || data.conversation || data || [];
      const ordered = list.slice().reverse();
      const frag = document.createDocumentFragment();
      ordered.forEach((m) => {
        if (!activeChat.messages.has(m.id)) {
          activeChat.messages.set(m.id, m);
          const isMe = m.is_mine || (m.sender?.username === currentUser);
          const row = document.createElement('div');
          row.className = `chat-row ${isMe ? 'me' : 'them'}`;
          row.dataset.id = m.id;
          row.innerHTML = `<div class="chat-bubble"><div class="chat-text">${escapeHtml(m.body || '')}</div><div class="chat-meta"><span>${timeAgo(m.created_at)}</span></div></div>`;
          frag.appendChild(row);
        }
      });
      messagesEl.insertBefore(frag, messagesEl.firstChild);
      activeChat.nextUrl = data.next || null;
      scrollContainer.scrollTop = scrollContainer.scrollHeight - prevHeight;
    } catch {}
  };
  scrollContainer.addEventListener('scroll', activeChat.onScroll);

  await loadInitial();
}

async function editMessage(m, bubble) {
  const newText = prompt('Edit message:', m.body || '');
  if (newText == null) return;
  const trimmed = newText.trim();
  if (!trimmed) return;
  try {
    const res = await authFetch(ENDPOINTS.messageEdit(m.id), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body: trimmed }),
    });
    m.body = trimmed;
    m.is_edited = true;
    const text = bubble.querySelector('.chat-text');
    if (text) text.textContent = trimmed;
    let meta = bubble.querySelector('.chat-meta');
    if (meta && !meta.textContent.includes('edited')) {
      const ed = document.createElement('span');
      ed.textContent = 'edited';
      meta.insertBefore(ed, meta.firstChild);
    }
  } catch (err) {
    showToast(`Unable to edit: ${err.message}`, 'error');
  }
}

async function deleteMessage(m, row) {
  if (!confirm('Delete this message?')) return;
  try {
    await authFetch(ENDPOINTS.messageDelete(m.id), { method: 'DELETE' });
    row.remove();
  } catch (err) {
    showToast(`Unable to delete: ${err.message}`, 'error');
  }
}

/* =================== EDIT PROFILE (ENHANCED) =================== */
async function showEditProfile() {
  const modal = document.getElementById('edit-profile-modal');
  if (!modal) return;
  try {
    const data = await authFetch('/api/v1/profile/me/');
    const profile = data || {};
    document.getElementById('edit-username').value = profile.username || '';
    document.getElementById('edit-email').value = profile.email || '';
    document.getElementById('edit-bio').value = profile.bio || '';
    const locEl = document.getElementById('edit-location');
    if (locEl) locEl.value = profile.location || '';
    const webEl = document.getElementById('edit-website');
    if (webEl) webEl.value = profile.website || '';
    const phoneEl = document.getElementById('edit-phone');
    if (phoneEl) phoneEl.value = profile.phone_number || '';
    const avatarPreview = document.getElementById('edit-avatar-preview');
    if (avatarPreview) {
      avatarPreview.src = profile.profile_image_url || getGravatarUrl(profile.email || '');
    }
    const fileInput = document.getElementById('edit-profile-pic');
    if (fileInput) {
      fileInput.value = '';
      fileInput.onchange = (e) => {
        const f = e.target.files[0];
        if (f && avatarPreview) avatarPreview.src = URL.createObjectURL(f);
      };
    }
    // Reset to first tab
    document.querySelectorAll('.edit-profile-tab').forEach((t, i) => t.classList.toggle('active', i === 0));
    document.querySelectorAll('.tabs-pane').forEach((p, i) => p.classList.toggle('active', i === 0));
    openModal('edit-profile-modal');
  } catch (err) {
    showToast(`Unable to load profile: ${err.message}`, 'error');
  }
}

async function handleEditProfile(e) {
  e.preventDefault();
  const form = e.target;
  const feedback = document.getElementById('edit-profile-feedback');
  const email = document.getElementById('edit-email').value.trim();
  const bio = document.getElementById('edit-bio').value.trim();
  const location = (document.getElementById('edit-location') || {}).value?.trim() || '';
  const website = (document.getElementById('edit-website') || {}).value?.trim() || '';
  const phone = (document.getElementById('edit-phone') || {}).value?.trim() || '';
  const fileInput = document.getElementById('edit-profile-pic');
  const file = fileInput?.files[0];
  const submitBtn = form.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  setFeedback(feedback, 'Saving…', false);
  try {
    const fd = new FormData();
    fd.append('email', email);
    if (bio) fd.append('bio', bio);
    if (location) fd.append('location', location);
    if (website) fd.append('website', website);
    if (phone) fd.append('phone_number', phone);
    if (file) fd.append('profile_image', file);

    const result = await authFetch(ENDPOINTS.settings, { method: 'PATCH', body: fd });
    setFeedback(feedback, 'Profile updated!', false);
    const imageUrl = result.profile_image_url || getGravatarUrl(email);
    setNavUser(currentUser, email, imageUrl);
    currentEmail = email;
    setTimeout(() => {
      setFeedback(feedback, '', false);
      closeModal('edit-profile-modal');
      loadProfileSummary();
    }, 700);
  } catch (err) {
    setFeedback(feedback, `Unable to update: ${err.message}`, true);
  } finally {
    submitBtn.disabled = false;
  }
}

async function handleChangePassword(e) {
  e.preventDefault();
  const form = e.target;
  const feedback = document.getElementById('password-feedback');
  const current_password = form.querySelector('#current-password').value;
  const new_password = form.querySelector('#new-password').value;
  const confirm_password = form.querySelector('#confirm-password').value;
  const submitBtn = form.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  setFeedback(feedback, 'Updating…', false);
  try {
    await authFetch(ENDPOINTS.passwordChange, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password, new_password, confirm_password }),
    });
    setFeedback(feedback, 'Password changed!', false);
    form.reset();
    setTimeout(() => {
      setFeedback(feedback, '', false);
      closeModal('edit-profile-modal');
    }, 1000);
  } catch (err) {
    const data = err.data || {};
    const msg = typeof data === 'object' ? Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join(' | ') : err.message;
    setFeedback(feedback, msg, true);
  } finally {
    submitBtn.disabled = false;
  }
}

document.addEventListener('click', (e) => {
  if (!e.target.closest('.btn-reaction') && !e.target.closest('.btn-comment-reaction')) {
    document.querySelectorAll('.reaction-picker.open, .comment-reaction-picker.open').forEach((p) => p.classList.remove('open'));
  }
});

document.addEventListener('DOMContentLoaded', init);
