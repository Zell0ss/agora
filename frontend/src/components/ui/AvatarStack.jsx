import Avatar from './Avatar'

export default function AvatarStack({ profiles = [], size = 26, ring }) {
  return (
    <div className="t-stack" style={ring ? { '--ring': ring } : undefined}>
      {profiles.map((p) => (
        <Avatar key={p.profile_id ?? p.id} profile={p} size={size} ring={ring} />
      ))}
    </div>
  )
}
