export default function Avatar({ profile, size = 34, ring }) {
  const isUser = !profile
  const cls = ['t-av', isUser ? 'is-user' : ''].filter(Boolean).join(' ')
  const style = { '--sz': size + 'px', fontSize: Math.round(size * 0.42) + 'px' }
  if (ring) style['--ring'] = ring

  return (
    <div
      className={cls}
      data-voice={isUser ? undefined : profile.color}
      style={style}
    >
      {isUser ? 'T' : (profile.name?.charAt(0) ?? '?')}
    </div>
  )
}
