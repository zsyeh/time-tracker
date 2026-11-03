(function () {
  'use strict'

  function cookie(name) {
    var prefix = name + '='
    var item = document.cookie.split('; ').find(function (part) { return part.indexOf(prefix) === 0 })
    return item ? decodeURIComponent(item.slice(prefix.length)) : ''
  }

  var status = document.getElementById('ip-handoff-status')
  var retry = document.getElementById('ip-handoff-retry')
  var token = window.location.hash.slice(1)
  history.replaceState(null, '', window.location.pathname)
  if (!/^drill_[A-Za-z0-9_-]{32,128}$/.test(token)) {
    status.textContent = '登录凭证缺失或格式无效，请重新发起 Passkey 登录。'
    retry.hidden = false
    return
  }

  fetch('/ip-auth/complete', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': cookie('csrftoken'),
    },
    body: JSON.stringify({ token: token }),
  }).then(function (response) {
    return response.json().catch(function () { return {} }).then(function (body) {
      if (!response.ok) throw new Error(body.detail || '登录凭证无效或已过期。')
      return body
    })
  }).then(function (body) {
    window.location.replace(body.redirect || '/')
  }).catch(function (error) {
    status.textContent = error.message + ' 请重新登录。'
    retry.hidden = false
  })
}())
