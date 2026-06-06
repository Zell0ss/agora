import Avatar from '../ui/Avatar'
import { useChannelStore } from '../../store/useChannelStore'

export default function ThinkingRow({ profileId }) {
  const roster = useChannelStore((s) => s.roster)
  const profile = roster.find((p) => p.profile_id === profileId)

  return (
    <div className="t-msg is-tert" data-voice={profile?.color ?? 'vera'}>
      <Avatar profile={profile} size={34} />
      <div className="t-msg-body">
        <div className="t-think-typing">
          <span className="t-msg-name">{profile?.name ?? '…'}</span> está pensando
          <span className="t-dots"><i /><i /><i /></span>
        </div>
      </div>
    </div>
  )
}
