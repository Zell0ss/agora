const BASE = '/api'

async function request(method, path, body) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const resp = await fetch(BASE + path, opts)
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(`${resp.status}: ${text}`)
  }
  if (resp.status === 204) return null
  return resp.json()
}

// Channels
export const getChannels = () => request('GET', '/channels')
export const createChannel = (body) => request('POST', '/channels', body)
export const getChannelMessages = (id) => request('GET', `/channels/${id}/messages`)
export const getRoster = (id) => request('GET', `/channels/${id}/profiles`)
export const addToRoster = (channelId, body) =>
  request('POST', `/channels/${channelId}/profiles`, body)
export const removeFromRoster = (channelId, profileId) =>
  request('DELETE', `/channels/${channelId}/profiles/${profileId}`)
export const deleteChannel = (id) => request('DELETE', `/channels/${id}`)

// Profiles
export const getProfiles = () => request('GET', '/profiles')
export const createProfile = (body) => request('POST', '/profiles', body)
export const patchProfile = (id, body) => request('PATCH', `/profiles/${id}`, body)
export const deleteProfile = (id) => request('DELETE', `/profiles/${id}`)
