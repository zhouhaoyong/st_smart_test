export function getRole(user) {
  if (user?.is_superuser) return 'super_admin'
  if (user?.is_manager) return 'manager'
  return 'user'
}

export function isAdmin(user) {
  const role = getRole(user)
  return role === 'super_admin' || role === 'manager'
}

export function canManageAll(user) {
  return isAdmin(user)
}

export function canCreateUser(currentUser) {
  return !!currentUser?.is_superuser
}

export function canManageUser(currentUser, targetUser) {
  if (!currentUser || !targetUser) return false
  return !!currentUser.is_superuser
}

export function canToggleUser(currentUser, targetUser) {
  if (!currentUser || !targetUser) return false
  if (!currentUser.is_superuser) return false
  if (currentUser.id === targetUser.id) return false
  if (targetUser.is_superuser && !currentUser.is_superuser) return false
  return true
}

export function canResetUserPassword(currentUser, targetUser) {
  return !!currentUser?.is_superuser && !!targetUser
}

export function canDeleteUser(currentUser, targetUser) {
  return !!currentUser?.is_superuser && !!targetUser && !targetUser.is_active
}

export function canManageResource(currentUser, row, options = {}) {
  if (!currentUser || !row) return false
  if (canManageAll(currentUser)) return true
  const ownerId = options.ownerId ?? row.owner_id
  const createdBy = options.createdBy ?? row.created_by
  const ownerName = options.ownerName ?? row.owner
  if (ownerId && ownerId === currentUser.id) return true
  if (createdBy && createdBy === currentUser.id) return true
  if (ownerName && ownerName === currentUser.real_name) return true
  return false
}
