import { useState, useEffect, useRef } from 'react';

import { 

  User,

  Camera,

  Image,

  Users, 

  UserCheck, Menu, 

  PlusCircle, 

  MessageSquare, 

  FileText, 

  Settings, 

  RefreshCw, 

  Trash2, 

  X, 

  Shield, 

  Bell,
  Bot,

  Database,

  Play,

  Pause,

  HelpCircle,

  BarChart2,

  Upload,

  Edit,

  Check,

  FileCheck,

  Key,

  Copy,

  ExternalLink,

  Eye,

  EyeOff,

  Lock,

  Search,

  Compass,

  Star,

  Send

} from 'lucide-react';



// Add global fetch interceptor to append authorization bearer token


const BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? (window.location.port === '5173' ? 'http://127.0.0.1:8000' : window.location.origin)
  : window.location.origin;

const originalFetch = window.fetch;

window.fetch = async (input, init) => {

  const token = localStorage.getItem('rosepay_auth_token') || sessionStorage.getItem('rosepay_auth_token');

  if (token && typeof input === 'string' && (input.includes('/api/') || input.startsWith('/api/'))) {

    init = init || {};

    init.headers = init.headers || {};

    if (init.headers instanceof Headers) {

      init.headers.set('Authorization', `Bearer ${token}`);

    } else if (Array.isArray(init.headers)) {

      const hasAuth = init.headers.some(([k]) => k.toLowerCase() === 'authorization');

      if (!hasAuth) {

        init.headers.push(['Authorization', `Bearer ${token}`]);

      }

    } else {

      if (!init.headers['Authorization'] && !init.headers['authorization']) {

        init.headers['Authorization'] = `Bearer ${token}`;

      }

    }

  }

  return originalFetch(input, init);

};



interface Account {

  phone: string;

  scraperUrl: string;

  status: 'idle' | 'sending_code' | 'waiting_code' | 'fetching_code' | 'submitting_code' | '2fa_required' | 'success' | 'failed';

  code: string;

  pass2fa: string;

  defaultPass2fa: string;

  statusText: string;

  accountId: string;

  pageId: string;

  showManual2fa: boolean;

}



interface Group {

  id: string;

  title: string;

  username: string;

  type: string;

  enabled: boolean;

  memberCount: number;

  category: string;

  quality_score?: number;

  relevance_score?: number;

  activity_score?: number;

  engagement_score?: number;

}



interface BatchResult {

  successCount: number;

  failedCount: number;

  errorDetails: string[];

}



interface LogEntry {

  time: string;

  folder: string;

  phone: string;

  title: string;

  action: string;

  status: 'success' | 'warning' | 'error';

  detail: string;

}

interface ManagedBot {
  id: number;
  bot_username: string;
  bot_token?: string;
  bot_type: string;
  title: string;
  description: string;
  is_active: number;
  created_at?: string;
  authorization_count?: number;
  auto_reply_count?: number;
  linked_accounts_count?: number;
}

interface BotAuthorization {
  telegram_chat_id: string;
  bot_type: string;
  telegram_username?: string;
  role: string;
  owner_username?: string;
  approved_at?: string;
  is_active: number;
}

interface BotAutoReply {
  id: number;
  bot_type: string;
  reply_text: string;
  is_enabled: number;
  created_at?: string;
}



export default function App() {

  // Navigation active tab

  const [activeTab, setActiveTab] = useState<'login' | 'accounts' | 'groups' | 'join' | 'campaign' | 'logs' | 'settings' | 'users' | 'permissions' | 'bot_auth' | 'templates' | 'scraper' | 'finder' | 'expansion'>('login');
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);

  useEffect(() => {
    setSidebarOpen(false);
  }, [activeTab]);



  // Scraper page states

  const [scraperPageId, setScraperPageId] = useState<string>(() => localStorage.getItem('rosepay_scraper_page_id') || 'aca5195e-d583-410a-9781-d51351c30083');

  const [scraperCode, setScraperCode] = useState<string>('');

  const [scraper2fa, setScraper2fa] = useState<string>('');

  const [scraperTime, setScraperTime] = useState<string>('');

  const [scraperLoading, setScraperLoading] = useState<boolean>(false);

  const [scraperError, setScraperError] = useState<string>('');

  const [isAutoPolling, setIsAutoPolling] = useState<boolean>(false);

  

  // Auth state

  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);

  const [isAdminInitialized, setIsAdminInitialized] = useState<boolean>(false);

  const [userRole, setUserRole] = useState<'admin' | 'user' | null>(null);

  const [currentUsername, setCurrentUsername] = useState<string>('');

  const [userCompany, setUserCompany] = useState<string>('');

  const [allowedTabs, setAllowedTabs] = useState<string[]>([]);
  const [accountViewScope, setAccountViewScope] = useState<'mine' | 'all'>('mine');
  const [selectedExpansionGroupDetail, setSelectedExpansionGroupDetail] = useState<any | null>(null);
  const [selectedScrapedGroupDetail, setSelectedScrapedGroupDetail] = useState<any | null>(null);
  const [groupToImportCategory, setGroupToImportCategory] = useState<any | null>(null);
  const [selectedImportCategory, setSelectedImportCategory] = useState<string>('中文广告');
  const scrapedLogsContainerRef = useRef<HTMLDivElement>(null);
  const [scrapedSortField, setScrapedSortField] = useState<'time' | 'member_count' | 'quality_score' | 'status'>('time');
  const [scrapedSortOrder, setScrapedSortOrder] = useState<'asc' | 'desc'>('desc');
  const [expansionSortField, setExpansionSortField] = useState<'time' | 'member_count' | 'quality_score'>('time');
  const [expansionSortOrder, setExpansionSortOrder] = useState<'asc' | 'desc'>('desc');
  const [groupCategories, setGroupCategories] = useState<{ id?: number; name: string; company: string }[]>([]);
  const [showManageCategoriesModal, setShowManageCategoriesModal] = useState<boolean>(false);
  const [newCategoryName, setNewCategoryName] = useState<string>('');

  const [rolePermissions, setRolePermissions] = useState<{ role: string, allowed_tabs: string[] }[]>([]);

  const [savingPermissions, setSavingPermissions] = useState<boolean>(false);



  // Ad templates state

  interface AdTemplate {

    id: number;

    description: string;

    content: string;

    group_type?: string;

  }

  const [adTemplates, setAdTemplates] = useState<AdTemplate[]>([]);

  const [newTemplateDesc, setNewTemplateDesc] = useState<string>('');

  const [newTemplateContent, setNewTemplateContent] = useState<string>('');

  const [editingAdId, setEditingAdId] = useState<number | null>(null);

  const [newTemplateGtype, setNewTemplateGtype] = useState<string>('英文短');

  const [selectedAdFilter, setSelectedAdFilter] = useState<string>('全部');

  

  // Login input states

  const [loginUsername, setLoginUsername] = useState<string>('');

  const [loginPassword, setLoginPassword] = useState<string>('');

  

  // Setup admin input states

  const [setupUsername, setSetupUsername] = useState<string>('');

  const [setupPassword, setSetupPassword] = useState<string>('');

  const [setupConfirmPassword, setSetupConfirmPassword] = useState<string>('');



  // User management states

  const [usersList, setUsersList] = useState<{id: number, username: string, role: string, company: string, telegram_contact?: string, created_at: string}[]>([]);

  const [showAddUserModal, setShowAddUserModal] = useState<boolean>(false);

  const [newUserUsername, setNewUserUsername] = useState<string>('');

  const [newUserPassword, setNewUserPassword] = useState<string>('');

  const [newUserRole, setNewUserRole] = useState<'admin' | 'user'>('user');

  const [newUserCompany, setNewUserCompany] = useState<string>('admin');

  const [newUserTelegramContact, setNewUserTelegramContact] = useState<string>('');

  const [showEditPasswordModal, setShowEditPasswordModal] = useState<boolean>(false);

  const [editPasswordTargetUser, setEditPasswordTargetUser] = useState<any | null>(null);

  const [editPasswordNewValue, setEditPasswordNewValue] = useState<string>('');

  const [editPasswordOldValue, setEditPasswordOldValue] = useState<string>('');



  // Edit user profile states

  const [showEditUserModal, setShowEditUserModal] = useState<boolean>(false);

  const [editUserTarget, setEditUserTarget] = useState<any | null>(null);

  const [editUserRole, setEditUserRole] = useState<'admin' | 'user'>('user');

  const [editUserCompany, setEditUserCompany] = useState<string>('');

  const [editUserPassword, setEditUserPassword] = useState<string>('');

  const [editUserTelegramContact, setEditUserTelegramContact] = useState<string>('');



  // Company management states

  const [companiesList, setCompaniesList] = useState<{id: number, name: string, created_at: string}[]>([]);

  const [showAddCompanyModal, setShowAddCompanyModal] = useState<boolean>(false);

  const [newCompanyName, setNewCompanyName] = useState<string>('');

  const [showEditCompanyModal, setShowEditCompanyModal] = useState<boolean>(false);

  const [editCompanyTarget, setEditCompanyTarget] = useState<any | null>(null);

  const [editCompanyNameValue, setEditCompanyNameValue] = useState<string>('');

  const [systemTabSubView, setSystemTabSubView] = useState<'users' | 'companies'>('users');

  const [managedBots, setManagedBots] = useState<ManagedBot[]>([]);
  const [selectedBotType, setSelectedBotType] = useState<string>('ai_bot');
  const [botAuthorizations, setBotAuthorizations] = useState<BotAuthorization[]>([]);
  const [botAutoReplies, setBotAutoReplies] = useState<BotAutoReply[]>([]);
  const [botsLoading, setBotsLoading] = useState<boolean>(false);
  const [showBotAuthModal, setShowBotAuthModal] = useState<boolean>(false);
  const [editingBotAuthChatId, setEditingBotAuthChatId] = useState<string | null>(null);
  const [botAuthChatId, setBotAuthChatId] = useState<string>('');
  const [botAuthUsername, setBotAuthUsername] = useState<string>('');
  const [botAuthRole, setBotAuthRole] = useState<string>('employee');
  const [botAuthOwner, setBotAuthOwner] = useState<string>('');
  const [botAuthActive, setBotAuthActive] = useState<number>(1);
  const [showBotReplyModal, setShowBotReplyModal] = useState<boolean>(false);
  const [editingBotReplyId, setEditingBotReplyId] = useState<number | null>(null);
  const [botReplyText, setBotReplyText] = useState<string>('');
  const [botReplyEnabled, setBotReplyEnabled] = useState<number>(1);
  const [showBotNodeModal, setShowBotNodeModal] = useState<boolean>(false);
  const [editingBotNode, setEditingBotNode] = useState<ManagedBot | null>(null);
  const [botNodeTitle, setBotNodeTitle] = useState<string>('');
  const [botNodeUsername, setBotNodeUsername] = useState<string>('');
  const [botNodeToken, setBotNodeToken] = useState<string>('');
  const [botNodeType, setBotNodeType] = useState<string>('ai_bot');
  const [botNodeDescription, setBotNodeDescription] = useState<string>('');
  const [botNodeActive, setBotNodeActive] = useState<number>(1);
  const [botManageTab, setBotManageTab] = useState<'auth' | 'reply'>('auth');



  // Interactive accounts pool state

  const [textareaValue, setTextareaValue] = useState<string>('');

  const [accountsPool, setAccountsPool] = useState<Account[]>([]);



  // Campaign state

  // Legacy states campaignFolder, taskInterval, groupInterval commented out for TS compilation

  /*

  const [campaignFolder, setCampaignFolder] = useState<string>('广告');

  const [taskInterval, setTaskInterval] = useState<number>(2);

  const [groupInterval, setGroupInterval] = useState<number>(5);

  */

  const [campaignMessage, setCampaignMessage] = useState<string>('');
  const [selectedAdTemplateIds, setSelectedAdTemplateIds] = useState<number[]>([]);
  const [campaignRunning] = useState<boolean>(false);



  // Auto-join state

  const [joinLinks, setJoinLinks] = useState<string>('');

  const [joinDelay, setJoinDelay] = useState<number | ''>(30);

  const [joinRunning, setJoinRunning] = useState<boolean>(false);

  const [selectedJoinAccounts, setSelectedJoinAccounts] = useState<string[]>([]);

  const [joinMode, setJoinMode] = useState<'simultaneous' | 'sequential'>('sequential');

  const [joinStrategy, setJoinStrategy] = useState<'fixed' | 'safety'>('fixed');

  const [joinSafetyGroups, setJoinSafetyGroups] = useState<number | ''>(5);

  const [joinSafetyMinutes, setJoinSafetyMinutes] = useState<number | ''>(30);

  const [joinTaskId, setJoinTaskId] = useState<string | null>(null);

  const [joinProgress, setJoinProgress] = useState<{current: number, total: number}>({current: 0, total: 0});

  const [joinResults, setJoinResults] = useState<any[]>([]);

  const [joinLogs, setJoinLogs] = useState<string[]>([]);

  const joinLogsContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {

    if (joinLogsContainerRef.current) {

      joinLogsContainerRef.current.scrollTop = joinLogsContainerRef.current.scrollHeight;

    }

  }, [joinLogs]);



  const [showInvalidGroupsModal, setShowInvalidGroupsModal] = useState<boolean>(false);

  const [invalidGroupsToDelete, setInvalidGroupsToDelete] = useState<{ id: string; title: string; link: string }[]>([]);

  const [moveJoinToFolder, setMoveJoinToFolder] = useState<boolean>(false);

  const [joinFolderByType, setJoinFolderByType] = useState<boolean>(true);

  const [joinTargetFolderName, setJoinTargetFolderName] = useState<string>('');

  const [joinMaxRounds, setJoinMaxRounds] = useState<number | ''>(() => {
    const saved = localStorage.getItem('rosepay_join_max_rounds');
    return saved ? parseInt(saved) : '';
  });

  const [joinGroupsPerRound, setJoinGroupsPerRound] = useState<number>(() => {
    const saved = localStorage.getItem('rosepay_join_groups_per_round');
    return saved ? parseInt(saved) : 10;
  });

  const [joinRoundInterval, setJoinRoundInterval] = useState<number>(() => {
    const saved = localStorage.getItem('rosepay_join_round_interval');
    return saved ? parseInt(saved) : 5;
  });

  useEffect(() => {
    localStorage.setItem('rosepay_join_max_rounds', joinMaxRounds === '' ? '' : joinMaxRounds.toString());
  }, [joinMaxRounds]);

  useEffect(() => {
    localStorage.setItem('rosepay_join_groups_per_round', joinGroupsPerRound.toString());
  }, [joinGroupsPerRound]);

  useEffect(() => {
    localStorage.setItem('rosepay_join_round_interval', joinRoundInterval.toString());
  }, [joinRoundInterval]);

  const [filterRestricted, setFilterRestricted] = useState<boolean>(false);

  const [taskHistoryList, setTaskHistoryList] = useState<any[]>([]);

  const [selectedHistoryTask, setSelectedHistoryTask] = useState<any | null>(null);

  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);



  // Settings state

  const [proxyEnabled, setProxyEnabled] = useState<boolean>(true);

  const [proxyHost, setProxyHost] = useState<string>('127.0.0.1');

  const [proxyPort, setProxyPort] = useState<number | ''>(8800);

  const [proxyUser, setProxyUser] = useState<string>('');

  const [proxyPass, setProxyPass] = useState<string>('');

  const [authMode, setAuthMode] = useState<'builtin' | 'api_hash'>('builtin');

  const [apiId, setApiId] = useState<string>('');

  const [apiHash, setApiHash] = useState<string>('');



  // Groups list state

  const [groups, setGroups] = useState<Group[]>([]);

  const [showAddGroupModal, setShowAddGroupModal] = useState<boolean>(false);

  const [newGroupLinks, setNewGroupLinks] = useState<string>('');

  const [resolvingGroup, setResolvingGroup] = useState<boolean>(false);

  const [newGroupCategory, setNewGroupCategory] = useState<string>('中文广告');

  const [showBatchResultModal, setShowBatchResultModal] = useState<boolean>(false);

  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);

  const [showGroupSyncSummaryModal, setShowGroupSyncSummaryModal] = useState<boolean>(false);

  const [groupSyncSummary, setGroupSyncSummary] = useState<GroupSyncSummary | null>(null);

  const [showGroupSyncExecutionModal, setShowGroupSyncExecutionModal] = useState<boolean>(false);

  const [groupSyncExecutionLogs, setGroupSyncExecutionLogs] = useState<string[]>([]);

  const [groupSyncRunning, setGroupSyncRunning] = useState<boolean>(false);

  const [groupSortField, setGroupSortField] = useState<'default' | 'quality' | 'members' | 'status' | 'title'>('default');

  const [groupSortOrder, setGroupSortOrder] = useState<'asc' | 'desc'>('desc');

  const [groupJoinTarget, setGroupJoinTarget] = useState<Group | null>(null);

  const [isBatchManaging, setIsBatchManaging] = useState<boolean>(false);

  const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([]);

  const [isBatchManagingAccounts, setIsBatchManagingAccounts] = useState<boolean>(false);

  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);

  const [batchEditTargetIds, setBatchEditTargetIds] = useState<string[]>([]);

  const [importedBatchSuccessIds, setImportedBatchSuccessIds] = useState<string[]>([]);

  const [showImportResultModal, setShowImportResultModal] = useState<boolean>(false);

  const [importStats, setImportStats] = useState<{ total: number; success: number; failed: number }>({ total: 0, success: 0, failed: 0 });

  const [showBatchProfileModal, setShowBatchProfileModal] = useState<boolean>(false);

  const [batchProfileLastName, setBatchProfileLastName] = useState<string>('RosePay');

  const [batchProfileVirtualModify, setBatchProfileVirtualModify] = useState<boolean>(true);

  const [batchProfileFirstName, setBatchProfileFirstName] = useState<string>('');

  const [batchProfileUsernamePrefix, setBatchProfileUsernamePrefix] = useState<string>('');

  const [batchProfileAbout, setBatchProfileAbout] = useState<string>('');

  const [updatingBatchProfiles, setUpdatingBatchProfiles] = useState<boolean>(false);



  // Avatar states

  const [showBatchAvatarModal, setShowBatchAvatarModal] = useState<boolean>(false);

  const [selectedAvatarFile, setSelectedAvatarFile] = useState<File | null>(null);

  const [batchAvatarFiles, setBatchAvatarFiles] = useState<FileList | null>(null);

  const [updatingAvatar, setUpdatingAvatar] = useState<boolean>(false);



  // Avatar Library states

  interface AvatarLibItem {

    name: string;

    size: number;

    mtime: number;

  }

  const [showLibraryManager, setShowLibraryManager] = useState<boolean>(false);

  const [avatarLibrary, setAvatarLibrary] = useState<AvatarLibItem[]>([]);

  const [uploadingToLibrary, setUploadingToLibrary] = useState<boolean>(false);

  const [singleAvatarSource, setSingleAvatarSource] = useState<'local' | 'library'>('local');

  const [selectedLibraryAvatarName, setSelectedLibraryAvatarName] = useState<string>('');

  const [selectedSingleAvatarFile, setSelectedSingleAvatarFile] = useState<File | null>(null);

  const [selectedSingleLibraryAvatarName, setSelectedSingleLibraryAvatarName] = useState<string>('');

  const [batchAvatarSource, setBatchAvatarSource] = useState<'local' | 'library'>('local');

  const [selectedBatchLibraryAvatarNames, setSelectedBatchLibraryAvatarNames] = useState<string[]>([]);

  const [renamingAvatarName, setRenamingAvatarName] = useState<string>('');

  const [renameAvatarInput, setRenameAvatarInput] = useState<string>('');



  // Import Batch Config Flow states

  const [isFromImportResult, setIsFromImportResult] = useState<boolean>(false);

  const [importBatchProfileCompleted, setImportBatchProfileCompleted] = useState<boolean>(false);

  const [importBatch2faCompleted, setImportBatch2faCompleted] = useState<boolean>(false);

  const [importBatchAvatarCompleted, setImportBatchAvatarCompleted] = useState<boolean>(false);

  const [importBatchBotCompleted, setImportBatchBotCompleted] = useState<boolean>(false);



  // Login Logs states

  const [showLoginLogsModal, setShowLoginLogsModal] = useState<boolean>(false);

  const [loginLogs, setLoginLogs] = useState<any[]>([]);



  // Dynamic Campaign Task states

  interface CampaignTask {

    id: string;

    account_id: string;

    phone: string;

    account_ids_json?: string;

    phones_json?: string;

    status: 'running' | 'stopped' | 'completed' | 'failed';

    max_cycles: number;

    current_cycle: number;

    round_interval_minutes: number;

    group_interval_seconds: number;

    is_safety: boolean;

    message: string;

    target_groups_json: string;

    success_count: number;

    fail_count: number;

    error_detail?: string;

    created_at: string;

    updated_at: string;

    created_by?: string;

    owner_username?: string;

  }

  interface GroupedCampaignTask {
    id: string;
    task_ids: string[];
    created_at: string;
    status: 'running' | 'completed' | 'stopped' | 'failed';
    max_cycles: number;
    current_cycle: number;
    round_interval_minutes: number;
    group_interval_seconds: number;
    is_safety: boolean;
    message: string;
    target_groups_json: string;
    success_count: number;
    fail_count: number;
    created_by?: string;
    owner_username?: string;
    phones: string[];
    subtasks: CampaignTask[];
  }

  const groupCampaignTasks = (tasks: CampaignTask[]): GroupedCampaignTask[] => {
    const groups: Record<string, GroupedCampaignTask> = {};
    tasks.forEach(task => {
      const key = `${task.created_at}_${task.round_interval_minutes}_${task.message.substring(0, 50)}`;
      let taskPhones = [task.phone];
      if (task.phones_json) {
        try {
          const parsedPhones = JSON.parse(task.phones_json);
          if (parsedPhones && typeof parsedPhones === 'object') {
            taskPhones = Object.values(parsedPhones).map(String).filter(Boolean);
          }
        } catch (e) {}
      }
      if (!groups[key]) {
        groups[key] = {
          id: task.id,
          task_ids: [task.id],
          created_at: task.created_at,
          status: task.status,
          max_cycles: task.max_cycles,
          current_cycle: task.current_cycle,
          round_interval_minutes: task.round_interval_minutes,
          group_interval_seconds: task.group_interval_seconds,
          is_safety: task.is_safety,
          message: task.message,
          target_groups_json: task.target_groups_json,
          success_count: task.success_count,
          fail_count: task.fail_count,
          created_by: task.created_by,
          owner_username: task.owner_username,
          phones: taskPhones,
          subtasks: [task]
        };
      } else {
        const g = groups[key];
        g.task_ids.push(task.id);
        taskPhones.forEach((phone) => {
          if (!g.phones.includes(phone)) {
            g.phones.push(phone);
          }
        });
        g.subtasks.push(task);
        g.success_count += task.success_count;
        g.fail_count += task.fail_count;
        g.current_cycle = Math.max(g.current_cycle, task.current_cycle);
        
        const statuses = g.subtasks.map(s => s.status);
        if (statuses.includes('running')) {
          g.status = 'running';
        } else if (statuses.includes('failed')) {
          g.status = 'failed';
        } else if (statuses.includes('stopped')) {
          g.status = 'stopped';
        } else {
          g.status = 'completed';
        }
      }
    });
    return Object.values(groups).sort((a, b) => b.created_at.localeCompare(a.created_at));
  };

  const [campaignTasks, setCampaignTasks] = useState<CampaignTask[]>([]);

  const [showCreateCampaignModal, setShowCreateCampaignModal] = useState<boolean>(false);

  const [campaignMaxCycles, setCampaignMaxCycles] = useState<number | ''>(0); 

  const [campaignRoundInterval, setCampaignRoundInterval] = useState<number | ''>(60);

  const [campaignGroupInterval, setCampaignGroupInterval] = useState<number | ''>(10);

  const [campaignIsSafety, setCampaignIsSafety] = useState<boolean>(false);

  const [campaignMultiAccountSafety, setCampaignMultiAccountSafety] = useState<boolean>(true);

  const [campaignStrategyEnabled, setCampaignStrategyEnabled] = useState<boolean>(false);

  

  const [newCampaignAccountId, setNewCampaignAccountId] = useState<string>('');
  const [campaignInputMode, setCampaignInputMode] = useState<'folders' | 'library' | 'manual'>('folders');

  const [selectedCampaignAccountIds, setSelectedCampaignAccountIds] = useState<string[]>([]);

  const [selectedCampaignFolderNames, setSelectedCampaignFolderNames] = useState<string[]>([]);



  const [campaignGroupListText, setCampaignGroupListText] = useState<string>('');

  const [loadingCampaignFoldersGroups, setLoadingCampaignFoldersGroups] = useState<boolean>(false);

  const [campaignFoldersGroups, setCampaignFoldersGroups] = useState<Record<string, Array<{ chat_id: number; title: string; username: string }>>>({});

  const [selectedCampaignGroupIds, setSelectedCampaignGroupIds] = useState<number[]>([]);

  const [selectedCampaignLibraryGroupIds, setSelectedCampaignLibraryGroupIds] = useState<string[]>([]);

  

  const [showCampaignLogsModal, setShowCampaignLogsModal] = useState<boolean>(false);

  const [activeCampaignTaskId, setActiveCampaignTaskId] = useState<string | null>(null);

  const [activeCampaignTaskLogs, setActiveCampaignTaskLogs] = useState<any[]>([]);

  const [showingHistoryCampaignsOnly, setShowingHistoryCampaignsOnly] = useState<boolean>(false);



  // Logs state

  // Logs state

  const [logs, setLogs] = useState<LogEntry[]>([
    { time: '14:25:31', folder: '广告', phone: '+91 89743 20586', title: '印度首码分享群', action: '发送广告', status: 'success', detail: '发送成功' },
    { time: '14:20:12', folder: '广告', phone: '+91 89743 20586', title: 'RosePay 返利交流中心', action: '发送广告', status: 'success', detail: '发送成功' },
    { time: '14:15:00', folder: '广告', phone: '+91 89743 20586', title: 'Telegram 自动粉群', action: '发送广告', status: 'warning', detail: '群禁言中，已自动跳过' },
    { time: '14:10:05', folder: '系统', phone: '+91 89743 20586', title: '系统连接', action: '账号校验', status: 'success', detail: 'Session校验通过，账号在线' },
  ]);

  const [selectedLogTaskId, setSelectedLogTaskId] = useState<string>('');
  const [selectedTaskLogs, setSelectedTaskLogs] = useState<any[]>([]);

  const fetchSelectedTaskLogs = async (taskId: string) => {
    if (!taskId) return;
    const grouped = groupCampaignTasks(campaignTasks);
    const group = grouped.find(g => g.task_ids.includes(taskId));
    const idsToFetch = group ? group.task_ids : [taskId];

    const backendUrl = BASE_URL;
    try {
      const allLogs = [];
      for (const tid of idsToFetch) {
        const res = await fetch(`${backendUrl}/api/campaign/tasks/${tid}/logs`);
        if (res.ok) {
          const data = await res.json();
          const taskObj = campaignTasks.find(t => t.id === tid);
          const phone = taskObj ? taskObj.phone : '';
          const tagged = data.map((log: any) => ({ ...log, phone: log.phone || phone }));
          allLogs.push(...tagged);
        }
      }
      allLogs.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
      setSelectedTaskLogs(allLogs);
    } catch (err) {
      console.error("加载任务日志失败", err);
    }
  };



  // Toast / Status notification count

  const [toastText, setToastText] = useState<string>('');



  // Calculate health score based on official SpamBot restriction status

  const calculateHealthScore = (acc: BackendAccount) => {

    if (!acc.isAuthorized || acc.is_deactivated) return 0;

    if (acc.spambot_status === 'restricted') return 50;

    if (acc.spambot_status === 'free') return 100;

    // Fallback if spambot status is not loaded yet or unknown

    return 100;

  };



  // Backend Accounts Management State

  interface BackendAccount {

    id: string;

    name: string;

    config: any;

    campaign_running: boolean;

    statusChecked?: boolean;

    isAuthorized?: boolean;

    is_connected?: boolean;
    
    busy_status?: 'idle' | 'join' | 'campaign' | 'scraper' | 'expansion' | 'unavailable';
    active_operation?: string | null;
    active_operation_label?: string | null;

    meInfo?: string;

    connection_status?: 'connected' | 'disconnected' | 'connecting' | 'error' | 'unknown';

    auth_status?: 'authorized' | 'unauthorized' | 'deactivated' | 'unknown';

    task_status?: string;

    availability_status?: 'available' | 'occupied';

    last_checked_at?: number | null;

    last_error?: string | null;

    isLoadingStatus?: boolean;

    spambot_status?: 'free' | 'restricted' | 'unknown' | 'error';

    spambot_details?: string;

    spambot_time?: number | null;

    is_deactivated?: boolean;

    bot_setup_status?: string;

    created_by?: string;
    company?: string;
    owner_username?: string;

    is_available?: boolean;

    private_listener?: boolean;

    private_listener_source?: string | null;

  }

  interface PrivateUnreadSummary {
    unread_dialogs: number;
    unread_messages: number;
    error?: string | null;
    updated_at?: number | null;
    loading?: boolean;
    stale?: boolean;
    busy?: boolean;
    external_unread_messages?: number;
    external_unread_dialogs?: number;
    last_private_event?: {
      sender_id?: number | string;
      sender_name?: string;
      sender_username?: string;
      message_id?: number | string;
      text?: string;
      source?: string;
      timestamp?: number;
      created_at?: number;
    } | null;
  }

  interface PrivateDmEvent {
    account_id: string;
    account_label?: string;
    account_owner_username?: string;
    account_created_by?: string;
    account_company?: string;
    sender_id?: number | string;
    sender_name?: string;
    sender_username?: string;
    sender_is_bot?: boolean;
    message_id?: number | string;
    text?: string;
    out?: boolean;
    notify?: boolean;
    source?: string;
    timestamp?: number;
    created_at?: number;
  }

  interface PrivateDialog {
    peer_id: string;
    name: string;
    username: string;
    phone: string;
    is_bot: boolean;
    unread_count: number;
    last_message: string;
    last_message_at: string | null;
  }

  interface PrivateMessage {
    id: number;
    text: string;
    out: boolean;
    date: string | null;
    has_media: boolean;
    status?: 'queued' | 'sent' | 'failed';
    queue_id?: string;
  }



  const [backendAccounts, setBackendAccounts] = useState<BackendAccount[]>([]);

  const [loadingAccounts, setLoadingAccounts] = useState<boolean>(false);

  const [accountSearchQuery, setAccountSearchQuery] = useState<string>('');
  const [isBotSetupLoading, setIsBotSetupLoading] = useState<boolean>(false);
  const [loadingBotAccounts, setLoadingBotAccounts] = useState<Record<string, boolean>>({});
  const [privateUnreadSummary, setPrivateUnreadSummary] = useState<Record<string, PrivateUnreadSummary>>({});
  const [privateRelayStarting, setPrivateRelayStarting] = useState<boolean>(false);
  const [showPrivateChatModal, setShowPrivateChatModal] = useState<boolean>(false);
  const [privateChatAccount, setPrivateChatAccount] = useState<BackendAccount | null>(null);
  const [privateDialogs, setPrivateDialogs] = useState<PrivateDialog[]>([]);
  const [selectedPrivateDialog, setSelectedPrivateDialog] = useState<PrivateDialog | null>(null);
  const [privateMessages, setPrivateMessages] = useState<PrivateMessage[]>([]);
  const [privateMessageDraft, setPrivateMessageDraft] = useState<string>('');
  const [loadingPrivateDialogs, setLoadingPrivateDialogs] = useState<boolean>(false);
  const [loadingPrivateMessages, setLoadingPrivateMessages] = useState<boolean>(false);
  const [sendingPrivateMessage, setSendingPrivateMessage] = useState<boolean>(false);
  const [privateChatError, setPrivateChatError] = useState<string>('');
  const showPrivateChatModalRef = useRef<boolean>(false);
  const privateChatAccountRef = useRef<BackendAccount | null>(null);
  const selectedPrivateDialogRef = useRef<PrivateDialog | null>(null);
  const seenPrivateEventKeysRef = useRef<Set<string>>(new Set());
  const backendAccountsRef = useRef<BackendAccount[]>([]);
  const currentUsernameRef = useRef<string>('');
  const privateMessageRequestSeqRef = useRef<number>(0);
  const openPrivateChatFromEventRef = useRef<(event: PrivateDmEvent) => void>(() => {});
  const privateMessagesEndRef = useRef<HTMLDivElement | null>(null);
  const [accountSortField, setAccountSortField] = useState<'health' | 'available' | 'none'>('health');

  const [accountSortDesc, setAccountSortDesc] = useState<boolean>(true);

  const privateRelayActive = backendAccounts.some(acc => Boolean(acc.private_listener));

  useEffect(() => {
    showPrivateChatModalRef.current = showPrivateChatModal;
    privateChatAccountRef.current = privateChatAccount;
    selectedPrivateDialogRef.current = selectedPrivateDialog;
    backendAccountsRef.current = backendAccounts;
    currentUsernameRef.current = currentUsername;
  }, [showPrivateChatModal, privateChatAccount, selectedPrivateDialog, backendAccounts, currentUsername]);

  const buildAccountFromPrivateEvent = (event: PrivateDmEvent): BackendAccount | null => {
    const accountId = String(event.account_id || '');
    if (!accountId) return null;
    return {
      id: accountId,
      name: event.account_label || `+${accountId}`,
      config: {
        owner_username: event.account_owner_username || '',
        created_by: event.account_created_by || ''
      },
      campaign_running: false,
      company: event.account_company || '',
      owner_username: event.account_owner_username || '',
      created_by: event.account_created_by || ''
    };
  };

  const sortPrivateDialogsByLatest = (dialogs: PrivateDialog[]) => {
    return [...dialogs].sort((a, b) => {
      const aTime = a.last_message_at ? new Date(a.last_message_at).getTime() : 0;
      const bTime = b.last_message_at ? new Date(b.last_message_at).getTime() : 0;
      if (bTime !== aTime) return bTime - aTime;
      return String(a.name || a.username || a.peer_id).localeCompare(String(b.name || b.username || b.peer_id));
    });
  };

  useEffect(() => {
    if (!showPrivateChatModal || !selectedPrivateDialog) return;
    requestAnimationFrame(() => {
      privateMessagesEndRef.current?.scrollIntoView({ block: 'end', behavior: 'auto' });
    });
  }, [showPrivateChatModal, selectedPrivateDialog?.peer_id, privateMessages.length, loadingPrivateMessages]);

  useEffect(() => {
    // Automatically remove accounts that truly cannot run tasks from task selections.
    // Short read-only operations, such as loading folders after selecting an account,
    // should not make the checked account disappear from the picker.
    const unavailableIds = backendAccounts
      .filter(acc => {
        const state = getAccountTaskState(acc);
        return state === 'join' ||
          state === 'campaign' ||
          state === 'scraper' ||
          state === 'expansion' ||
          state === 'unavailable' ||
          state === 'offline';
      })
      .map(acc => acc.id);
      
    if (unavailableIds.length > 0) {
      setSelectedCampaignAccountIds(prev => {
        const next = prev.filter(id => !unavailableIds.includes(id));
        if (next.length !== prev.length) {
          if (next.length === 1) {
            setNewCampaignAccountId(next[0]);
          } else {
            setNewCampaignAccountId('');
          }
          return next;
        }
        return prev;
      });
      
      setSelectedJoinAccounts(prev => {
        const next = prev.filter(id => !unavailableIds.includes(id));
        return next;
      });
    }
  }, [backendAccounts]);

  const getAccountTaskState = (acc: BackendAccount): 'idle' | 'join' | 'campaign' | 'scraper' | 'expansion' | 'operation' | 'unavailable' | 'offline' => {
    if (acc.active_operation) return 'operation';
    if (acc.busy_status && acc.busy_status !== 'idle') return acc.busy_status;
    if (acc.is_available === false) return 'unavailable';
    if (!acc.isAuthorized || acc.is_deactivated) return 'offline';
    return 'idle';
  };

  const isAccountSelectableForTask = (acc: BackendAccount) => getAccountTaskState(acc) === 'idle';
  const isAccountLockedForManualOperation = (acc: BackendAccount) => {
    const state = getAccountTaskState(acc);
    return state === 'operation' || state === 'join' || state === 'campaign' || state === 'scraper' || state === 'expansion';
  };

  const togglePrivateRelayListeners = async () => {
    if (privateRelayStarting) return;
    setPrivateRelayStarting(true);
    try {
      const endpoint = privateRelayActive
        ? `${BASE_URL}/api/accounts/private-listeners/stop`
        : `${BASE_URL}/api/accounts/private-listeners/start-idle`;
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `启动失败：${res.status}`);
      }
      if (data.disabled) {
        setToastText(data.message || '实时私聊中转未启用');
      } else if (privateRelayActive) {
        const stopped = Array.isArray(data.stopped) ? data.stopped.length : 0;
        const skipped = Array.isArray(data.skipped) ? data.skipped.length : 0;
        setToastText(`私聊中转已关闭：停止 ${stopped} 个，跳过 ${skipped} 个`);
      } else {
        const started = Array.isArray(data.started) ? data.started.length : 0;
        const skipped = Array.isArray(data.skipped) ? data.skipped.length : 0;
        const failed = Array.isArray(data.failed) ? data.failed.length : 0;
        setToastText(`私聊中转启动完成：已监听 ${started} 个，跳过 ${skipped} 个，失败 ${failed} 个`);
      }
      setTimeout(() => setToastText(''), 4500);
      await fetchBackendAccounts(false);
      await fetchPrivateUnreadSummary(false);
    } catch (err: any) {
      setToastText(err?.message || (privateRelayActive ? '关闭私聊中转失败' : '启动私聊中转失败'));
      setTimeout(() => setToastText(''), 4500);
    } finally {
      setPrivateRelayStarting(false);
    }
  };
  const shouldShowAccountUnlockButton = (acc: BackendAccount) => Boolean(acc.active_operation);

  const getAccountSortBucket = (acc: BackendAccount): number => {
    if (acc.is_available === false) return 3;
    if (acc.active_operation) return 2;
    if (acc.busy_status && acc.busy_status !== 'idle') return 2;
    if (!acc.isAuthorized || acc.is_deactivated) return 1;
    return 0;
  };

  const getAccountTaskStateLabel = (acc: BackendAccount) => {
    const state = getAccountTaskState(acc);
    if (state === 'join') return '该账号正在自动加群';
    if (state === 'campaign') return '该账号正在轰炸';
    if (state === 'scraper') return '该账号正在智能搜群';
    if (state === 'expansion') return '该账号正在业务拓展';
    if (state === 'operation') return `该账号正在${acc.active_operation_label || '执行操作'}`;
    if (state === 'unavailable') return '账号已占用';
    if (state === 'offline') return '账号未登录';
    return '';
  };

  const applyAccountStatusPatch = (accountId: string, patch: any) => {
    setBackendAccounts(prev => prev.map(acc => {
      if (acc.id !== accountId) return acc;
      const next: BackendAccount = {
        ...acc,
        ...patch,
        isAuthorized: patch.is_authorized !== undefined ? patch.is_authorized : (patch.isAuthorized !== undefined ? patch.isAuthorized : acc.isAuthorized),
        meInfo: patch.me !== undefined ? patch.me : (patch.meInfo !== undefined ? patch.meInfo : acc.meInfo),
        isLoadingStatus: patch.isLoadingStatus !== undefined ? patch.isLoadingStatus : acc.isLoadingStatus,
      };
      if (patch.config) {
        next.config = { ...acc.config, ...patch.config };
      }
      return next;
    }));
  };

  useEffect(() => {
    if (!isLoggedIn) return;
    const token = localStorage.getItem('rosepay_auth_token') || sessionStorage.getItem('rosepay_auth_token');
    if (!token) return;

    const streamUrl = `${BASE_URL}/api/account-status/stream?token=${encodeURIComponent(token)}`;
    const source = new EventSource(streamUrl);

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'initial' && Array.isArray(data.accounts)) {
          data.accounts.forEach((item: any) => {
            if (item?.account_id && item?.patch) {
              applyAccountStatusPatch(item.account_id, item.patch);
            }
          });
          return;
        }
        if (data.type === 'account_status' && data.account_id && data.patch) {
          applyAccountStatusPatch(data.account_id, data.patch);
        }
      } catch (err) {
        console.error('Failed to apply account status event:', err);
      }
    };

    source.onerror = () => {
      // EventSource reconnects automatically; keep a quiet console breadcrumb for debugging.
      console.warn('Account status stream disconnected; browser will retry.');
    };

    return () => {
      source.close();
    };
  }, [isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) return;
    const token = localStorage.getItem('rosepay_auth_token') || sessionStorage.getItem('rosepay_auth_token');
    if (!token) return;
    const privateStreamStartedAt = Date.now() / 1000;

    const makePrivateEventKey = (event: PrivateDmEvent) => {
      const accountId = String(event.account_id || '');
      const senderId = String(event.sender_id || '');
      const messageId = String(event.message_id || '');
      if (accountId && senderId && messageId && messageId !== '0') {
        return `${accountId}:${senderId}:${messageId}`;
      }
      return `${accountId}:${senderId}:${event.timestamp || event.created_at || ''}:${event.text || ''}`;
    };

    const isBotPrivateEvent = (event: PrivateDmEvent) => {
      if (event.sender_is_bot) return true;
      const username = String(event.sender_username || '').trim().replace(/^@/, '').toLowerCase();
      return Boolean(username && username.endsWith('bot'));
    };

    const applyPrivateDmEvent = (event: PrivateDmEvent) => {
      const accountId = String(event.account_id || '');
      const peerId = String(event.sender_id || '');
      if (event.out || event.notify === false || isBotPrivateEvent(event)) return;
      if (!accountId || !peerId) return;
      const eventTime = Number(event.created_at || event.timestamp || 0);
      if (eventTime > 0 && eventTime < privateStreamStartedAt - 1) return;

      const key = makePrivateEventKey(event);
      if (seenPrivateEventKeysRef.current.has(key)) return;
      seenPrivateEventKeysRef.current.add(key);
      if (seenPrivateEventKeysRef.current.size > 1000) {
        seenPrivateEventKeysRef.current = new Set(Array.from(seenPrivateEventKeysRef.current).slice(-500));
      }

      const isOpenAccount = showPrivateChatModalRef.current && privateChatAccountRef.current?.id === accountId;
      const isSelectedDialog = isOpenAccount && selectedPrivateDialogRef.current?.peer_id === peerId;
      const eventDate = event.timestamp ? new Date(event.timestamp * 1000).toISOString() : new Date().toISOString();
      const messageIdNumber = Number(event.message_id || 0) || -Math.floor((event.timestamp || Date.now()) * 1000);
      const displayName = event.sender_name || event.sender_username || 'Unknown';
      setPrivateUnreadSummary(prev => {
        const base = prev[accountId] || { unread_dialogs: 0, unread_messages: 0 };
        const nextMessages = isSelectedDialog ? 0 : Number(base.unread_messages || 0) + 1;
        const nextDialogs = isSelectedDialog ? 0 : Math.max(1, Number(base.unread_dialogs || 0));
        return {
          ...prev,
          [accountId]: {
            ...base,
            unread_messages: nextMessages,
            unread_dialogs: nextDialogs,
            external_unread_messages: nextMessages,
            external_unread_dialogs: nextDialogs,
            last_private_event: event,
            loading: false,
            stale: false,
            updated_at: Date.now() / 1000
          }
        };
      });

      if (!isOpenAccount) return;

      setPrivateDialogs(prev => {
        const nextDialog: PrivateDialog = {
          peer_id: peerId,
          name: displayName,
          username: event.sender_username || '',
          phone: '',
          is_bot: false,
          unread_count: isSelectedDialog ? 0 : 1,
          last_message: event.text || '[media]',
          last_message_at: eventDate
        };
        const existing = prev.find(item => item.peer_id === peerId);
        const rest = prev.filter(item => item.peer_id !== peerId);
        if (existing) {
          nextDialog.phone = existing.phone;
          nextDialog.is_bot = existing.is_bot;
          nextDialog.unread_count = isSelectedDialog ? 0 : Number(existing.unread_count || 0) + 1;
        }
        return sortPrivateDialogsByLatest([nextDialog, ...rest]);
      });

      if (isSelectedDialog) {
        void fetch(`${BASE_URL}/api/accounts/${accountId}/private-dm-events/read`, { method: 'POST' });
        setPrivateMessages(prev => {
          if (prev.some(msg => msg.id === messageIdNumber)) return prev;
          return [
            ...prev,
            {
              id: messageIdNumber,
              text: event.text || '',
              out: false,
              date: eventDate,
              has_media: !event.text
            }
          ];
        });
      }
    };

    const streamUrl = `${BASE_URL}/api/private-dm/stream?token=${encodeURIComponent(token)}`;
    const source = new EventSource(streamUrl);
    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'private_dm' && data.event) {
          applyPrivateDmEvent(data.event);
        }
      } catch (err) {
        console.error('Failed to apply private DM event:', err);
      }
    };
    source.onerror = () => {
      console.warn('Private DM stream disconnected; browser will retry.');
    };
    return () => {
      source.close();
    };
  }, [isLoggedIn]);



  // Custom Confirmation Dialog State

  interface CustomConfirmConfig {

    title?: string;

    message: string;

    onConfirm: () => void | Promise<void>;

    onCancel?: () => void;

    confirmText?: string;

    cancelText?: string;

    type?: 'info' | 'warning' | 'danger';

  }

  const [customConfirm, setCustomConfirm] = useState<CustomConfirmConfig | null>(null);



  const checkAuthStatus = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/auth/status`);

      if (res.ok) {

        const data = await res.json();

        setIsAdminInitialized(data.initialized);

      }

    } catch (err) {

      console.error("Failed to check auth status:", err);

    }

  };

  const handleToggleAccountAvailableStatus = async (accountId: string) => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/toggle-status`, {

        method: 'POST'

      });

      if (res.ok) {

        const data = await res.json();

        setBackendAccounts(prev => prev.map(acc => {

          if (acc.id === accountId) {

            return { ...acc, is_available: data.is_available };

          }

          return acc;

        }));

      } else {

        const errData = await res.json();

        alert(`切换账号状态失败: ${errData.detail || '未知原因'}`);

      }

    } catch (err: any) {

      console.error("Failed to toggle account available status:", err);

      alert(`切换账号状态异常: ${err.message}`);

    }

  };



  const checkCurrentUser = async () => {

    const backendUrl = BASE_URL;

    const token = localStorage.getItem('rosepay_auth_token') || sessionStorage.getItem('rosepay_auth_token');

    if (!token) {

      setIsLoggedIn(false);

      return;

    }

    try {

      const res = await fetch(`${backendUrl}/api/auth/current`);

      if (res.ok) {

        const user = await res.json();

        setCurrentUsername(user.username);

        setUserRole(user.role);

        setUserCompany(user.company || '');
        setAccountViewScope(user.username === 'eason' ? 'all' : 'mine');

        setAllowedTabs([...(user.allowed_tabs || []), 'finder', 'expansion']);

        setIsLoggedIn(true);

      } else {

        localStorage.removeItem('rosepay_auth_token');

        sessionStorage.removeItem('rosepay_auth_token');

        setIsLoggedIn(false);

      }

    } catch (err) {

      console.error("Failed to fetch current user:", err);

      setIsLoggedIn(false);

    }

  };



  const handleLoginSubmit = async () => {

    if (!loginUsername.trim() || !loginPassword) {

      alert("请输入用户名和密码");

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/auth/login`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({ username: loginUsername.trim(), password: loginPassword })

      });

      const data = await res.json();

      if (res.ok) {

        sessionStorage.setItem('rosepay_auth_token', data.token);

        localStorage.setItem('rosepay_auth_token', data.token);

        setCurrentUsername(data.username);

        setUserRole(data.role);

        setUserCompany(data.company || '');
        const initialAccountScope = data.username === 'eason' ? 'all' : 'mine';
        setAccountViewScope(initialAccountScope);

        setAllowedTabs([...(data.allowed_tabs || []), 'finder', 'expansion']);

        setIsLoggedIn(true);

        setToastText("登录成功");

        setTimeout(() => setToastText(''), 2000);

        fetchBackendAccounts(false, initialAccountScope);

        fetchGroups();

      } else {

        alert(`登录失败: ${data.detail || '密码错误'}`);

      }

    } catch (err: any) {

      alert(`登录发生异常: ${err.message}`);

    }

  };



  const fetchUsersList = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/admin/users`);

      if (res.ok) {

        const data = await res.json();

        setUsersList(data);

      }

    } catch (err) {

      console.error("Failed to fetch users list:", err);

    }

  };



  const fetchCompaniesList = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/admin/companies`);

      if (res.ok) {

        const data = await res.json();

        setCompaniesList(data);

      }

    } catch (err) {

      console.error("Failed to fetch companies list:", err);

    }

  };



  const handleCreateCompany = async () => {

    if (!newCompanyName.trim()) {

      alert("公司名称不能为空");

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/admin/companies`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({ name: newCompanyName.trim() })

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("创建公司成功");

        setTimeout(() => setToastText(''), 2000);

        setShowAddCompanyModal(false);

        setNewCompanyName('');

        fetchCompaniesList();

      } else {

        alert(`创建失败: ${data.detail}`);

      }

    } catch (err: any) {

      alert(`创建异常: ${err.message}`);

    }

  };



  const handleUpdateCompany = async () => {

    if (!editCompanyTarget) return;

    if (!editCompanyNameValue.trim()) {

      alert("公司名称不能为空");

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/admin/companies/${editCompanyTarget.id}`, {

        method: 'PUT',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({ name: editCompanyNameValue.trim() })

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("修改公司成功");

        setTimeout(() => setToastText(''), 2000);

        setShowEditCompanyModal(false);

        setEditCompanyTarget(null);

        setEditCompanyNameValue('');

        fetchCompaniesList();

      } else {

        alert(`修改失败: ${data.detail}`);

      }

    } catch (err: any) {

      alert(`修改异常: ${err.message}`);

    }

  };



  const handleDeleteCompany = async (companyId: number, companyName: string) => {

    if (companyName === 'admin') {

      alert("不能删除admin");

      return;

    }

    if (!confirm(`确定要删除公司 "${companyName}" 吗？这需要该公司下没有任何系统用户和 Telegram 账号。`)) {

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/admin/companies/${companyId}`, {

        method: 'DELETE'

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("删除公司成功");

        setTimeout(() => setToastText(''), 2000);

        fetchCompaniesList();

      } else {

        alert(`删除失败: ${data.detail}`);

      }

    } catch (err: any) {

      alert(`删除异常: ${err.message}`);

    }

  };



  const fetchRolePermissions = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/admin/permissions`);

      if (res.ok) {

        const data = await res.json();

        setRolePermissions(data);

      }

    } catch (err) {

      console.error("Failed to fetch role permissions:", err);

    }

  };



  const handleCreateUser = async () => {

    if (!newUserUsername.trim() || newUserPassword.length < 6) {

      alert("用户名不能为空，密码长度必须不小于 6 位");

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/admin/users`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          username: newUserUsername.trim(),

          password: newUserPassword,

          role: newUserRole,

          company: newUserCompany,

          telegram_contact: newUserTelegramContact.trim()

        })

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("创建用户成功");

        setTimeout(() => setToastText(''), 2000);

        setShowAddUserModal(false);

        setNewUserUsername('');

        setNewUserPassword('');

        setNewUserCompany('admin');

        setNewUserTelegramContact('');

        fetchUsersList();

      } else {

        alert(`创建失败: ${data.detail}`);

      }

    } catch (err: any) {

      alert(`创建异常: ${err.message}`);

    }

  };



  const handleDeleteUser = async (userId: number, usernameToDelete: string) => {

    if (usernameToDelete === currentUsername) {

      alert("不能删除当前登录的账户");

      return;

    }

    if (!confirm(`确定要删除用户 "${usernameToDelete}" 吗？`)) {

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/admin/users/${userId}`, {

        method: 'DELETE'

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("删除用户成功");

        setTimeout(() => setToastText(''), 2000);

        fetchUsersList();

      } else {

        alert(`删除失败: ${data.detail}`);

      }

    } catch (err: any) {

      alert(`删除异常: ${err.message}`);

    }

  };



  const handleUpdateUser = async () => {

    if (!editUserTarget) return;

    const backendUrl = BASE_URL;

    if (editUserPassword && editUserPassword.length < 6) {

      alert("密码长度必须不小于 6 位");

      return;

    }

    try {

      const payload: any = {

        role: editUserRole,

        company: editUserCompany,

        telegram_contact: editUserTelegramContact.trim()

      };

      if (editUserPassword) {

        payload.password = editUserPassword;

      }

      const res = await fetch(`${backendUrl}/api/admin/users/${editUserTarget.id}`, {

        method: 'PUT',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify(payload)

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("更新用户成功");

        setTimeout(() => setToastText(''), 2000);

        setShowEditUserModal(false);

        setEditUserTarget(null);

        setEditUserPassword('');

        setEditUserTelegramContact('');

        fetchUsersList();

      } else {

        alert(`更新失败: ${data.detail}`);

      }

    } catch (err: any) {

      alert(`更新异常: ${err.message}`);

    }

  };



  const handleUpdateUserPassword = async (userId: number, newPasswordVal: string, oldPasswordVal?: string) => {

    if (newPasswordVal.length < 6) {

      alert("新密码长度不能小于 6 位");

      return;

    }

    if (editPasswordTargetUser && editPasswordTargetUser.username === currentUsername) {

      if (!oldPasswordVal) {

        alert("请输入原密码");

        return;

      }

      if (oldPasswordVal.length < 6) {

        alert("原密码长度不能小于 6 位");

        return;

      }

      if (newPasswordVal === oldPasswordVal) {

        alert("新密码不能与原密码相同");

        return;

      }

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/admin/users/${userId}/password`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          old_password: oldPasswordVal || "",

          password: newPasswordVal

        })

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("用户密码修改成功");

        setTimeout(() => setToastText(''), 2000);

        setShowEditPasswordModal(false);

        setEditPasswordNewValue('');

        setEditPasswordOldValue('');

        setEditPasswordTargetUser(null);

        fetchUsersList();

      } else {

        alert(`修改密码失败: ${data.detail}`);

      }

    } catch (err: any) {

      alert(`修改密码异常: ${err.message}`);

    }

  };




  const fetchManagedBots = async () => {
    setBotsLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/api/bots`);
      if (res.ok) {
        const data = await res.json();
        const bots = Array.isArray(data) ? data : (Array.isArray(data.bots) ? data.bots : []);
        setManagedBots(bots);
        if (bots.length > 0 && !bots.some((b: ManagedBot) => b.bot_type === selectedBotType)) {
          setSelectedBotType(bots[0].bot_type || 'ai_bot');
        }
      }
    } catch (err) {
      console.error('Failed to fetch bots', err);
    } finally {
      setBotsLoading(false);
    }
  };

  const fetchBotAuthorizations = async (botType: string = selectedBotType) => {
    try {
      const res = await fetch(`${BASE_URL}/api/bots/${encodeURIComponent(botType)}/authorizations`);
      if (res.ok) {
        const data = await res.json();
        setBotAuthorizations(Array.isArray(data) ? data : (Array.isArray(data.authorizations) ? data.authorizations : []));
      }
    } catch (err) {
      console.error('Failed to fetch bot authorizations', err);
    }
  };

  const fetchBotAutoReplies = async (botType: string = selectedBotType) => {
    try {
      const res = await fetch(`${BASE_URL}/api/bots/${encodeURIComponent(botType)}/auto-replies`);
      if (res.ok) {
        const data = await res.json();
        setBotAutoReplies(Array.isArray(data) ? data : (Array.isArray(data.replies) ? data.replies : []));
      }
    } catch (err) {
      console.error('Failed to fetch bot auto replies', err);
    }
  };

  const isTranslateBotType = (botType?: string | null) => (botType || '').toLowerCase() === 'translate_bot';

  const refreshBotPermissionPage = async (botType: string = selectedBotType) => {
    await Promise.all([
      fetchManagedBots(),
      fetchBotAuthorizations(botType),
      fetchBotAutoReplies(botType)
    ]);
  };

  const openCreateBotNodeModal = () => {
    setEditingBotNode(null);
    setBotNodeTitle('');
    setBotNodeUsername('');
    setBotNodeToken('');
    setBotNodeType('ai_bot');
    setBotNodeDescription('');
    setBotNodeActive(1);
    setBotManageTab('auth');
    setShowBotNodeModal(true);
  };

  const openEditBotNodeModal = async (bot: ManagedBot, tab: 'auth' | 'reply' = 'auth') => {
    const botType = bot.bot_type || 'ai_bot';
    const translateBot = isTranslateBotType(botType);
    setEditingBotNode(bot);
    setBotNodeTitle(bot.title || '');
    setBotNodeUsername(bot.bot_username || '');
    setBotNodeToken(bot.bot_token || '');
    setBotNodeType(botType);
    setBotNodeDescription(bot.description || '');
    setBotNodeActive(bot.is_active ? 1 : 0);
    setSelectedBotType(botType);
    setBotManageTab(translateBot ? 'auth' : tab);
    setShowBotNodeModal(true);
    if (translateBot) {
      setBotAutoReplies([]);
      await fetchBotAuthorizations(botType);
    } else {
      await Promise.all([
        fetchBotAuthorizations(botType),
        fetchBotAutoReplies(botType)
      ]);
    }
  };

  const saveBotNode = async (e?: any) => {
    e?.preventDefault();
    if (!botNodeTitle.trim() || !botNodeUsername.trim() || !botNodeToken.trim()) {
      alert('Bot 节点名称、用户名和 Token 不能为空');
      return;
    }
    try {
      const url = editingBotNode
        ? `${BASE_URL}/api/bots/${editingBotNode.id}`
        : `${BASE_URL}/api/bots`;
      const res = await fetch(url, {
        method: editingBotNode ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: botNodeTitle.trim(),
          bot_username: botNodeUsername.trim(),
          bot_token: botNodeToken.trim(),
          bot_type: botNodeType,
          description: botNodeDescription.trim(),
          is_active: botNodeActive
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || '保存失败');
      setToastText(editingBotNode ? 'Bot 节点已更新' : 'Bot 节点已创建');
      setTimeout(() => setToastText(''), 2000);
      setShowBotNodeModal(false);
      await fetchManagedBots();
    } catch (err: any) {
      alert(`保存 Bot 节点失败: ${err.message}`);
    }
  };

  const deleteBotNode = async (bot: ManagedBot) => {
    if (!confirm(`确定删除 Bot 节点「${bot.title || bot.bot_username}」吗？`)) return;
    try {
      const res = await fetch(`${BASE_URL}/api/bots/${bot.id}`, { method: 'DELETE' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || '删除失败');
      setShowBotNodeModal(false);
      await fetchManagedBots();
    } catch (err: any) {
      alert(`删除 Bot 节点失败: ${err.message}`);
    }
  };

  const openCreateBotAuthModal = () => {
    setEditingBotAuthChatId(null);
    setBotNodeType(selectedBotType);
    setBotAuthChatId('');
    setBotAuthUsername('');
    setBotAuthRole('employee');
    setBotAuthOwner('');
    setBotAuthActive(1);
    setShowBotAuthModal(true);
  };

  const openEditBotAuthModal = (auth: BotAuthorization) => {
    setEditingBotAuthChatId(auth.telegram_chat_id);
    setBotAuthChatId(auth.telegram_chat_id || '');
    setBotAuthUsername(auth.telegram_username || '');
    setBotAuthRole(auth.role || 'employee');
    setBotAuthOwner(auth.owner_username || '');
    setBotAuthActive(auth.is_active ? 1 : 0);
    setShowBotAuthModal(true);
  };

  const saveBotAuthorization = async () => {
    if (!botAuthChatId.trim()) {
      alert('电报 Chat ID 不能为空');
      return;
    }
    try {
      const method = editingBotAuthChatId ? 'PUT' : 'POST';
      const url = editingBotAuthChatId
        ? `${BASE_URL}/api/bots/${encodeURIComponent(selectedBotType)}/authorizations/${encodeURIComponent(editingBotAuthChatId)}`
        : `${BASE_URL}/api/bots/${encodeURIComponent(selectedBotType)}/authorizations`;
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          telegram_chat_id: botAuthChatId.trim(),
          telegram_username: botAuthUsername.trim(),
          role: botAuthRole,
          owner_username: botAuthOwner.trim(),
          is_active: botAuthActive
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(`保存授权失败: ${data.detail || '未知错误'}`);
        return;
      }
      setShowBotAuthModal(false);
      setToastText('Bot 授权已保存');
      setTimeout(() => setToastText(''), 2000);
      fetchBotAuthorizations(selectedBotType);
      fetchManagedBots();
    } catch (err: any) {
      alert(`保存授权异常: ${err.message}`);
    }
  };

  const deleteBotAuthorization = async (auth: BotAuthorization) => {
    if (!confirm(`确定删除 ${auth.telegram_chat_id} 的 Bot 授权吗？`)) return;
    try {
      const res = await fetch(`${BASE_URL}/api/bots/${encodeURIComponent(selectedBotType)}/authorizations/${encodeURIComponent(auth.telegram_chat_id)}`, { method: 'DELETE' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(`删除授权失败: ${data.detail || '未知错误'}`);
        return;
      }
      fetchBotAuthorizations(selectedBotType);
      fetchManagedBots();
    } catch (err: any) {
      alert(`删除授权异常: ${err.message}`);
    }
  };

  const openCreateBotReplyModal = () => {
    setEditingBotReplyId(null);
    setBotReplyText('');
    setBotReplyEnabled(1);
    setShowBotReplyModal(true);
  };

  const openEditBotReplyModal = (reply: BotAutoReply) => {
    setEditingBotReplyId(reply.id);
    setBotReplyText(reply.reply_text || '');
    setBotReplyEnabled(reply.is_enabled ? 1 : 0);
    setShowBotReplyModal(true);
  };

  const saveBotAutoReply = async () => {
    if (!botReplyText.trim()) {
      alert('自动回复内容不能为空');
      return;
    }
    try {
      const method = editingBotReplyId ? 'PUT' : 'POST';
      const url = editingBotReplyId
        ? `${BASE_URL}/api/bots/${encodeURIComponent(selectedBotType)}/auto-replies/${editingBotReplyId}`
        : `${BASE_URL}/api/bots/${encodeURIComponent(selectedBotType)}/auto-replies`;
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reply_text: botReplyText.trim(), is_enabled: botReplyEnabled })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(`保存自动回复失败: ${data.detail || '未知错误'}`);
        return;
      }
      setShowBotReplyModal(false);
      setToastText('Bot 自动回复已保存');
      setTimeout(() => setToastText(''), 2000);
      fetchBotAutoReplies(selectedBotType);
      fetchManagedBots();
    } catch (err: any) {
      alert(`保存自动回复异常: ${err.message}`);
    }
  };

  const deleteBotAutoReply = async (reply: BotAutoReply) => {
    if (!confirm('确定删除这条自动回复模板吗？')) return;
    try {
      const res = await fetch(`${BASE_URL}/api/bots/${encodeURIComponent(selectedBotType)}/auto-replies/${reply.id}`, { method: 'DELETE' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(`删除自动回复失败: ${data.detail || '未知错误'}`);
        return;
      }
      fetchBotAutoReplies(selectedBotType);
      fetchManagedBots();
    } catch (err: any) {
      alert(`删除自动回复异常: ${err.message}`);
    }
  };

  const fetchCampaignLogs = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/campaign/logs?limit=50`);

      if (res.ok) {

        const data = await res.json();

        const mappedLogs = data.map((log: any) => ({

          time: log.time,

          folder: log.folder,

          phone: log.chat_id || 'System',

          title: log.title,

          action: log.action,

          status: log.status === 'success' ? 'success' : (log.status === 'warning' || log.status === 'skipped') ? 'warning' : 'error',

          detail: log.detail

        }));

        setLogs(mappedLogs);

      }

    } catch (err) {

      console.error("Failed to fetch logs:", err);

    }

  };



  const fetchLastJoinTask = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/groups/join-task/last`);

      if (res.ok) {

        const data = await res.json();

        if (data.status && data.status !== 'none') {

          setJoinTaskId(data.task_id);

          setJoinProgress(data.progress || { current: 0, total: 0 });

          setJoinResults(data.results || []);

          setJoinLogs(data.logs || []);

          if (data.status === 'running') {

            setJoinRunning(true);

            setSelectedHistoryTask(null); // Clear history task to show the live execution board

          } else {

            setJoinRunning(false);

          }



          // 只在有“正在运行”的任务时才回填当初配置的参数

          if (data.status === 'running' && data.params) {

            if (data.params.account_ids) setSelectedJoinAccounts(data.params.account_ids);

            // if (data.params.links) setJoinLinks(data.params.links.join('\n'));

            if (data.params.mode) setJoinMode(data.params.mode);

            if (data.params.strategy) setJoinStrategy(data.params.strategy);

            if (data.params.fixed_delay) setJoinDelay(data.params.fixed_delay);

            if (data.params.safety_groups) setJoinSafetyGroups(data.params.safety_groups);

            if (data.params.safety_minutes) setJoinSafetyMinutes(data.params.safety_minutes);

            if (data.params.move_to_folder !== undefined) setMoveJoinToFolder(data.params.move_to_folder);

            if (data.params.folder_by_type !== undefined) setJoinFolderByType(data.params.folder_by_type);

            if (data.params.target_folder_name) setJoinTargetFolderName(data.params.target_folder_name);

          }

        }

      }

    } catch (err) {

      console.error("Failed to fetch last join task:", err);

    }

  };



  const fetchTaskHistory = async () => {

    const backendUrl = BASE_URL;

    setLoadingHistory(true);

    try {

      const res = await fetch(`${backendUrl}/api/groups/join-task/history`);

      if (res.ok) {

        const data = await res.json();

        setTaskHistoryList(data || []);

      }

    } catch (err) {

      console.error("Failed to fetch join task history:", err);

    } finally {

      setLoadingHistory(false);

    }

  };



  const fetchHistoryTaskDetail = async (taskId: string) => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/groups/join-task/history/${taskId}`);

      if (res.ok) {

        const data = await res.json();

        setSelectedHistoryTask(data);

      } else {

        alert("无法加载历史任务详情");

      }

    } catch (err: any) {

      alert(`加载历史详情失败: ${err.message}`);

    }

  };





  const fetchScraperData = async (pid?: string) => {

    const targetPid = pid || scraperPageId;

    if (!targetPid) return;

    

    // Auto extract UUID if full URL is pasted

    let uuid = targetPid.trim();

    const urlMatch = uuid.match(/(?:https?:\/\/[^\/]+\/)?([a-zA-Z0-9\-]+)(?:\/GetHTML)?/);

    if (urlMatch) {

      uuid = urlMatch[1];

    }



    setScraperLoading(true);

    setScraperError('');

    

    try {

      const backendUrl = BASE_URL;

      const res = await fetch(`${backendUrl}/api/scraper/fetch?page_id=${uuid}`);

      if (!res.ok) {

        throw new Error('拉取失败，请检查 Page ID 是否有效');

      }

      const data = await res.json();

      setScraperCode(data.code || '');

      setScraper2fa(data.pass2fa || '');

      setScraperTime(data.login_time || '');

    } catch (err: any) {

      setScraperError(err.message || '网络请求错误');

    } finally {

      setScraperLoading(false);

    }

  };



  useEffect(() => {

    let interval: any;

    if (activeTab === 'scraper' && isAutoPolling && scraperPageId) {

      fetchScraperData(scraperPageId);

      interval = setInterval(() => {

        fetchScraperData(scraperPageId);

      }, 3000);

    }

    return () => {

      if (interval) clearInterval(interval);

    };

  }, [activeTab, isAutoPolling, scraperPageId]);





  const fetchBackendAccounts = async (forceRefresh: boolean = false, scopeOverride?: 'mine' | 'all') => {

    setLoadingAccounts(true);
    if (forceRefresh) {
      setToastText('正在同步账号状态...');
    }

    const backendUrl = BASE_URL;
    const scope = scopeOverride || accountViewScope;

    try {

      const res = await fetch(`${backendUrl}/api/accounts?scope=${encodeURIComponent(scope)}`);

      if (res.ok) {

        const data: any[] = await res.json();

        const mappedData: BackendAccount[] = data.map(acc => ({

          ...acc,

          isAuthorized: acc.is_authorized !== undefined ? acc.is_authorized : acc.isAuthorized,

          statusChecked: true

        }));

        setBackendAccounts(mappedData);

        

        // If forceRefresh is true, update the status of each account sequentially to prevent server overload

        if (forceRefresh) {

          for (let i = 0; i < mappedData.length; i++) {

            setToastText(`正在同步账号状态 ${i + 1}/${mappedData.length}...`);
            await checkAccountLoginStatus(mappedData[i].id, i, false);

          }

          const refreshedRes = await fetch(`${backendUrl}/api/accounts?scope=${encodeURIComponent(scope)}`);
          if (refreshedRes.ok) {
            const refreshedData: any[] = await refreshedRes.json();
            const refreshedMappedData: BackendAccount[] = refreshedData.map(acc => ({
              ...acc,
              isAuthorized: acc.is_authorized !== undefined ? acc.is_authorized : acc.isAuthorized,
              statusChecked: true
            }));
            setBackendAccounts(refreshedMappedData);
          }

        }

        if (forceRefresh) {
          await fetchPrivateUnreadSummary(false, scope);
          setToastText('账号状态同步完成');
          setTimeout(() => setToastText(''), 2500);
        }

      } else {

        if (forceRefresh) {
          setToastText(`同步账号状态失败：${res.status}`);
          setTimeout(() => setToastText(''), 3000);
        }

      }

    } catch (err) {

      console.error("Failed to fetch backend accounts:", err);
      if (forceRefresh) {
        setToastText('同步账号状态失败，请检查登录状态或网络');
        setTimeout(() => setToastText(''), 3000);
      }

    } finally {

      setLoadingAccounts(false);

    }

  };


  const fetchPrivateUnreadSummary = async (force: boolean = false, scopeOverride?: 'mine' | 'all') => {
    try {
      const scope = scopeOverride || accountViewScope;
      const params = new URLSearchParams();
      params.set('scope', scope);
      if (force) params.set('force', 'true');
      const res = await fetch(`${BASE_URL}/api/accounts/private-unread-summary?${params.toString()}`);
      if (!res.ok) return;
      const data = await res.json();
      setPrivateUnreadSummary(data || {});
    } catch (err) {
      console.error('Failed to fetch private unread summary:', err);
    }
  };

  useEffect(() => {
    if (isLoggedIn && activeTab === 'accounts') {
      fetchPrivateUnreadSummary();
      const timer = window.setInterval(() => fetchPrivateUnreadSummary(), 60000);
      return () => window.clearInterval(timer);
    }
  }, [isLoggedIn, activeTab, backendAccounts.length, accountViewScope]);

  const fetchPrivateDialogs = async (accountId: string, preferredPeerId?: string, keepCurrentSelection: boolean = false) => {
    setLoadingPrivateDialogs(true);
    setPrivateChatError('');
    let dialogListReady = false;
    try {
      const res = await fetch(`${BASE_URL}/api/accounts/${accountId}/private-dialogs?limit=30`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `加载私聊失败：${res.status}`);
      }
      const data = await res.json();
      const dialogs: PrivateDialog[] = data.dialogs || [];
      const sortedDialogs = sortPrivateDialogsByLatest(dialogs);
      setPrivateDialogs(sortedDialogs);
      setLoadingPrivateDialogs(false);
      dialogListReady = true;
      if (!keepCurrentSelection && sortedDialogs.length > 0) {
        const preferredDialog = preferredPeerId ? sortedDialogs.find(dialog => dialog.peer_id === preferredPeerId) : null;
        void handleSelectPrivateDialog(accountId, preferredDialog || sortedDialogs[0]);
      } else if (!keepCurrentSelection) {
        setSelectedPrivateDialog(null);
        setPrivateMessages([]);
      }
    } catch (err: any) {
      setPrivateChatError(err?.message || '加载私聊失败');
    } finally {
      if (!dialogListReady) {
        setLoadingPrivateDialogs(false);
      }
    }
  };

  const handleOpenPrivateChatModal = async (account: BackendAccount, eventOverride?: PrivateDmEvent) => {
    setPrivateChatAccount(account);
    setShowPrivateChatModal(true);
    setPrivateUnreadSummary(prev => ({
      ...prev,
      [account.id]: {
        ...(prev[account.id] || { unread_dialogs: 0, unread_messages: 0 }),
        unread_dialogs: 0,
        unread_messages: 0,
        external_unread_dialogs: 0,
        external_unread_messages: 0,
        last_private_event: null,
        loading: false,
        stale: false
      }
    }));
    setPrivateDialogs([]);
    setSelectedPrivateDialog(null);
    setPrivateMessages([]);
    setPrivateMessageDraft('');
    const lastEvent = eventOverride || privateUnreadSummary[account.id]?.last_private_event;
    if (lastEvent) {
      const eventDate = lastEvent.timestamp ? new Date(lastEvent.timestamp * 1000).toISOString() : new Date().toISOString();
      const quickDialog: PrivateDialog = {
        peer_id: String((lastEvent as any).sender_id || ''),
        name: lastEvent.sender_name || lastEvent.sender_username || 'Unknown',
        username: lastEvent.sender_username || '',
        phone: '',
        is_bot: false,
        unread_count: 1,
        last_message: lastEvent.text || '[无文本]',
        last_message_at: eventDate
      };
      if (quickDialog.peer_id) {
        setPrivateDialogs([quickDialog]);
        setSelectedPrivateDialog(quickDialog);
        setPrivateMessages([{
          id: -Math.floor((lastEvent.timestamp || Date.now()) * 1000),
          text: lastEvent.text || '[无文本]',
          out: false,
          date: eventDate,
          has_media: !lastEvent.text
        }]);
      }
    }
    void fetchPrivateDialogs(account.id, lastEvent ? String((lastEvent as any).sender_id || '') : undefined);
  };

  openPrivateChatFromEventRef.current = (event: PrivateDmEvent) => {
    const accountId = String(event.account_id || '');
    const account = backendAccountsRef.current.find(item => item.id === accountId) || buildAccountFromPrivateEvent(event);
    if (!account) {
      setToastText('当前用户没有权限查看这个账号的私聊');
      setTimeout(() => setToastText(''), 3000);
      return;
    }
    setActiveTab('accounts');
    handleOpenPrivateChatModal(account, event);
  };

  const handleSelectPrivateDialog = async (accountId: string, dialog: PrivateDialog) => {
    const requestSeq = privateMessageRequestSeqRef.current + 1;
    privateMessageRequestSeqRef.current = requestSeq;
    setSelectedPrivateDialog(dialog);
    setPrivateMessages([]);
    setLoadingPrivateMessages(true);
    setPrivateChatError('');
    try {
      const res = await fetch(`${BASE_URL}/api/accounts/${accountId}/private-dialogs/${dialog.peer_id}/messages?limit=30`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `加载消息失败：${res.status}`);
      }
      const data = await res.json();
      if (privateMessageRequestSeqRef.current !== requestSeq) return;
      setPrivateMessages(data.messages || []);
      setPrivateDialogs(prev => sortPrivateDialogsByLatest(prev.map(item => item.peer_id === dialog.peer_id ? { ...item, unread_count: 0 } : item)));
      setPrivateUnreadSummary(prev => ({
        ...prev,
        [accountId]: {
          ...(prev[accountId] || { unread_dialogs: 0, unread_messages: 0 }),
          unread_dialogs: 0,
          unread_messages: 0,
          external_unread_dialogs: 0,
          external_unread_messages: 0,
          last_private_event: null,
          loading: false,
          stale: false,
          updated_at: Date.now() / 1000
        }
      }));
      fetchPrivateUnreadSummary();
    } catch (err: any) {
      if (privateMessageRequestSeqRef.current !== requestSeq) return;
      setPrivateChatError(err?.message || '加载消息失败');
    } finally {
      if (privateMessageRequestSeqRef.current === requestSeq) {
        setLoadingPrivateMessages(false);
      }
    }
  };

  const handleSendPrivateMessage = async () => {
    if (!privateChatAccount || !selectedPrivateDialog || !privateMessageDraft.trim()) return;
    setSendingPrivateMessage(true);
    setPrivateChatError('');
    try {
      const res = await fetch(`${BASE_URL}/api/accounts/${privateChatAccount.id}/private-dialogs/${selectedPrivateDialog.peer_id}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: privateMessageDraft.trim() })
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `发送失败：${res.status}`);
      }
      const data = await res.json();
      if (data.message) {
        setPrivateMessages(prev => [...prev, data.message]);
        setPrivateDialogs(prev => sortPrivateDialogsByLatest(prev.map(item => (
          item.peer_id === selectedPrivateDialog.peer_id
            ? {
                ...item,
                last_message: data.message.text || (data.message.has_media ? '[media]' : item.last_message),
                last_message_at: data.message.date || new Date().toISOString(),
                unread_count: 0
              }
            : item
        ))));
      }
      if (data.notice) {
        setToastText(data.notice);
        setTimeout(() => setToastText(''), 3000);
      }
      setPrivateMessageDraft('');
      if (!data.queued) {
        fetchPrivateDialogs(privateChatAccount.id, selectedPrivateDialog.peer_id, true);
      }
    } catch (err: any) {
      setPrivateChatError(err?.message || '发送失败');
    } finally {
      setSendingPrivateMessage(false);
    }
  };

  const checkAccountLoginStatus = async (accountId: string, index: number, force: boolean = false) => {

    setBackendAccounts(prev => prev.map((acc, idx) => idx === index ? { ...acc, isLoadingStatus: true } : acc));

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/login/status/${accountId}?force=${force}`);

      if (res.ok) {

        const data = await res.json();

        setBackendAccounts(prev => prev.map((acc, idx) => idx === index ? { 

          ...acc, 

          statusChecked: true,

          isAuthorized: data.is_authorized,

          meInfo: data.me || data.error || (data.is_deactivated ? '账号已被官方注销 (Deactivated)' : '未登录'),

          isLoadingStatus: false,

          spambot_status: data.spambot_status,

          spambot_details: data.spambot_details,

          spambot_time: data.spambot_time,

          is_deactivated: data.is_deactivated,

          bot_setup_status: data.bot_setup_status || acc.bot_setup_status

        } : acc));

      }

    } catch (err) {

      setBackendAccounts(prev => prev.map((acc, idx) => idx === index ? { 

        ...acc, 

        statusChecked: true,

        isAuthorized: false,

        meInfo: '连接状态失败',

        isLoadingStatus: false

      } : acc));

    }

  };



  const handleRefreshHealthDetails = async (accountId: string) => {

    setCheckingHealth(true);

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/login/status/${accountId}?force=true`);

      if (res.ok) {

        const data = await res.json();

        // Update in backendAccounts list

        setBackendAccounts(prev => prev.map(acc => acc.id === accountId ? {

          ...acc,

          statusChecked: true,

          isAuthorized: data.is_authorized,

          meInfo: data.me || data.error || (data.is_deactivated ? '账号已被官方注销 (Deactivated)' : '未登录'),

          spambot_status: data.spambot_status,

          spambot_details: data.spambot_details,

          spambot_time: data.spambot_time,

          is_deactivated: data.is_deactivated,

          bot_setup_status: data.bot_setup_status || acc.bot_setup_status

        } : acc))



        // Also update currently displayed account in modal

        setHealthDetailsAccount(prev => prev && prev.id === accountId ? {

          ...prev,

          statusChecked: true,

          isAuthorized: data.is_authorized,

          meInfo: data.me || data.error || (data.is_deactivated ? '账号已被官方注销 (Deactivated)' : '未登录'),

          spambot_status: data.spambot_status,

          spambot_details: data.spambot_details,

          spambot_time: data.spambot_time,

          is_deactivated: data.is_deactivated,

          bot_setup_status: data.bot_setup_status || prev.bot_setup_status

        } : prev)

      }

    } catch (err) {

      console.error("Failed to refresh health details:", err);

    } finally {

      setCheckingHealth(false);

    }

  };



  const handleSyncAccountProfile = async (accountId: string) => {

    setBackendAccounts(prev => prev.map(acc => acc.id === accountId ? { ...acc, isLoadingStatus: true } : acc));

    setToastText(`正在同步账号 +${accountId} 的个人信息与用户名...`);

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/login/status/${accountId}?force=true`);

      if (res.ok) {

        const data = await res.json();

        setBackendAccounts(prev => prev.map(acc => acc.id === accountId ? {
          ...acc,
          statusChecked: true,
          isAuthorized: data.is_authorized,
          is_connected: data.is_connected,
          meInfo: data.me || data.error || (data.is_deactivated ? '账号已被官方注销 (Deactivated)' : '未登录'),
          spambot_status: data.spambot_status,
          spambot_details: data.spambot_details,
          spambot_time: data.spambot_time,
          is_deactivated: data.is_deactivated,
          bot_setup_status: data.bot_setup_status || acc.bot_setup_status,
          isLoadingStatus: false
        } : acc));

        setToastText(`账号 +${accountId} 信息同步完成`);

        setTimeout(() => setToastText(''), 2000);

        await fetchBackendAccounts();

      } else {

        const data = await res.json();

        alert(`同步失败: ${data.detail || '未知原因'}`);

      }

    } catch (err: any) {

      alert(`同步异常: ${err.message}`);

    } finally {

      setBackendAccounts(prev => prev.map(acc => acc.id === accountId ? { ...acc, isLoadingStatus: false } : acc));

    }

  };



  const handleToggleProfileModified = async (accountId: string) => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/toggle-profile-modified`, {

        method: 'POST'

      });

      if (res.ok) {

        const data = await res.json();

        setBackendAccounts(prev => prev.map(acc => {

          if (acc.id === accountId) {

            const updatedConfig = { ...acc.config, profile_modified: data.profile_modified };

            return { ...acc, config: updatedConfig };

          }

          return acc;

        }));

      }

    } catch (err) {

      console.error("Failed to toggle profile modified status:", err);

    }

  };



  ;

  const handleConfigureBotDirectly = async (account: BackendAccount) => {
    setLoadingBotAccounts(prev => ({ ...prev, [account.id]: true }));
    try {
      const res = await fetch(`${BASE_URL}/api/accounts/${account.id}/bot/start`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        const nextStatus = data.bot_setup_status || 'approved';
        setBackendAccounts(prev => prev.map(a =>
          a.id === account.id ? {
            ...a,
            bot_setup_status: nextStatus,
            config: {
              ...a.config,
              bot_setup_status: nextStatus
            }
          } : a
        ));
        setToastText('BOT 配置及审批已自动完成');
        setTimeout(() => setToastText(''), 2000);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`自动配Bot失败: ${err.detail || '未知错误'}`);
      }
    } catch (e: any) {
      alert(`自动配Bot发生异常: ${e.message}`);
    } finally {
      setLoadingBotAccounts(prev => ({ ...prev, [account.id]: false }));
    }
  };

  const handleSetAccountOwner = async (accountId: string, ownerUsername: string) => {
    const backendUrl = BASE_URL;
    try {
      const acc = backendAccounts.find(t => t.id === accountId);
      if (!acc) return;
      const proxy = acc.config?.proxy || {
        enabled: acc.config?.proxy_enabled ?? false,
        type: acc.config?.proxy_type ?? 'socks5',
        host: acc.config?.proxy_host ?? '127.0.0.1',
        port: acc.config?.proxy_port ?? 8800,
        username: acc.config?.proxy_username ?? '',
        password: acc.config?.proxy_password ?? ''
      };
      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/config`, {
        method: 'POST',
        headers: { "Content-Type": 'application/json' },
        body: JSON.stringify({
          account_name: acc.config?.account_name || acc.name || accountId,
          folder_name: acc.config?.folder_name || '广告',
          proxy,
          owner_username: ownerUsername.trim()
        })
      });
      if (res.ok) {
        setToastText('账号归属修改成功');
        setTimeout(() => setToastText(''), 2000);
        setBackendAccounts(prev => prev.map(a =>
          a.id === accountId ? { ...a, config: { ...a.config, owner_username: ownerUsername.trim(), proxy } } : a
        ));
        if (modalAccount && modalAccount.id === accountId) {
          setModalAccount(prev => prev ? { ...prev, config: { ...prev.config, owner_username: ownerUsername.trim(), proxy } } : null);
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        alert(`保存归属失败: ${errData.detail || '服务器返回了非 JSON 错误'}`);
      }
    } catch (err: any) {
      alert(`保存归属异常: ${err.message}`);
    }
  };

  const handleUpdateAccountProxy = async (accountId: string, host: string) => {
    const backendUrl = BASE_URL;
    try {
      const acc = backendAccounts.find(t => t.id === accountId);
      if (!acc) return;
      const proxy = host === 'none' ? {
        enabled: false,
        type: 'socks5',
        host: '127.0.0.1',
        port: 8800,
        username: '',
        password: ''
      } : {
        enabled: true,
        type: 'socks5',
        host,
        port: 50101,
        username: 'easonsenli',
        password: 'Mz8biy6nTn'
      };
      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/config`, {
        method: 'POST',
        headers: { "Content-Type": 'application/json' },
        body: JSON.stringify({
          account_name: acc.config?.account_name || acc.name || accountId,
          folder_name: acc.config?.folder_name || '广告',
          proxy,
          owner_username: acc.config?.owner_username || acc.created_by || acc.config?.created_by || 'rosepay'
        })
      });
      if (res.ok) {
        setToastText('代理配置更新成功');
        setTimeout(() => setToastText(''), 2000);
        setBackendAccounts(prev => prev.map(a =>
          a.id === accountId ? { ...a, config: { ...a.config, proxy } } : a
        ));
        if (modalAccount && modalAccount.id === accountId) {
          setModalAccount(prev => prev ? { ...prev, config: { ...prev.config, proxy } } : null);
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        alert(`更新代理失败: ${errData.detail || '服务器返回了非 JSON 错误'}`);
      }
    } catch (err: any) {
      alert(`更新代理异常: ${err.message}`);
    }
  };



  const handleDeleteBackendAccount = async (accountId: string) => {

    if (!confirm(`⚠️ 安全警示与警告：\n\n您正准备执行【彻底删除】账号操作！\n这将永久清除账号 ${accountId} 在本系统内的全部配置参数、电报登录会话（Session 文件）以及同步的文件夹与历史记录。\n\n删除后该账号将彻底下线，无法继续执行任务，必须重新接码登录。您确定要彻底删除该账号吗？`)) {

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}`, {

        method: 'DELETE'

      });

      if (res.ok) {

        setToastText(`账号 ${accountId} 已彻底删除`);

        setTimeout(() => setToastText(''), 2000);

        fetchBackendAccounts();

      } else {

        alert("删除失败");

      }

    } catch (err: any) {

      alert(`删除异常: ${err.message}`);

    }

  };



  const handleClearBackendAccountSession = async (accountId: string) => {

    if (!confirm(`确定要清除账号 ${accountId} 的 Session (强制退出登录) 吗？`)) {

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/clear-session`, {

        method: 'POST'

      });

      if (res.ok) {

        setToastText(`账号 ${accountId} 的 Session 已清除`);

        setTimeout(() => setToastText(''), 2000);

        fetchBackendAccounts();

      } else {

        alert("清除 Session 失败");

      }

    } catch (err: any) {

      alert(`清除 Session 异常: ${err.message}`);

    }

  };



  const handleTriggerBotSetup = async (account: BackendAccount) => {
    setIsBotSetupLoading(true);
    setToastText(`正在静默配置账号 +${account.id} 的翻译 Bot...`);
    try {
      const res = await fetch(`${BASE_URL}/api/accounts/${account.id}/bot/start`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        const nextStatus = data.bot_setup_status || 'approved';
        setBackendAccounts(prev => prev.map(acc => acc.id === account.id ? {
          ...acc,
          bot_setup_status: nextStatus,
          config: {
            ...acc.config,
            bot_setup_status: nextStatus
          }
        } : acc));
        setToastText(`账号 +${account.id} 翻译 Bot 已配置`);
      } else {
        const err = await res.json();
        alert(`配置失败: ${err.detail || '未知错误'}`);
      }
    } catch (e: any) {
      alert(`网络错误: ${e.message}`);
    } finally {
      setIsBotSetupLoading(false);
      setTimeout(() => setToastText(''), 3000);
    }
  };

  const handleBatchTriggerBotSetup = async (targetIds: string[] = selectedAccountIds, fromImportResult: boolean = false) => {
    if (targetIds.length === 0) return;
    setIsBotSetupLoading(true);
    setToastText(`正在批量配置 ${targetIds.length} 个账号的翻译 Bot...`);

    let successCount = 0;
    let failCount = 0;
    let skippedCount = 0;

    await Promise.all(targetIds.map(async (accountId) => {
      const acc = backendAccounts.find(a => a.id === accountId);
      if (!acc) {
        skippedCount++;
        return;
      }
      if (!acc.isAuthorized) {
        skippedCount++;
        return;
      }
      if ((acc.bot_setup_status || acc.config?.bot_setup_status) === 'approved') {
        skippedCount++;
        return;
      }

      try {
        const res = await fetch(`${BASE_URL}/api/accounts/${accountId}/bot/start`, {
          method: 'POST'
        });
        if (res.ok) {
          successCount++;
        } else {
          failCount++;
        }
      } catch (e) {
        failCount++;
      }
    }));

    await fetchBackendAccounts();
    setIsBotSetupLoading(false);

    let msg = `批量配置完成！成功: ${successCount} 个`;
    if (failCount > 0) msg += `，失败: ${failCount} 个`;
    if (skippedCount > 0) msg += `，跳过(未登录或已配置): ${skippedCount} 个`;

    setToastText(msg);
    setTimeout(() => setToastText(''), 4000);

    if (fromImportResult) {
      setImportBatchBotCompleted(true);
      setShowImportResultModal(true);
    }
  };

  const handleToggleSelectAccount = (accountId: string) => {
    const account = backendAccounts.find(acc => acc.id === accountId);
    if (account && isAccountLockedForManualOperation(account)) {
      setToastText(getAccountTaskStateLabel(account) || '该账号当前不可操作');
      setTimeout(() => setToastText(''), 2500);
      return;
    }

    setSelectedAccountIds(prev => 

      prev.includes(accountId) 

        ? prev.filter(id => id !== accountId) 

        : [...prev, accountId]

    );

  };



  const getFilteredAndSortedAccounts = () => {

    let result = [...backendAccounts];

    if (accountSearchQuery.trim()) {

      const query = accountSearchQuery.toLowerCase().trim();

      result = result.filter(acc => {

        const nameMatch = (acc.name || '').toLowerCase().includes(query);

        const phoneMatch = (acc.id || '').toLowerCase().includes(query);

        const infoMatch = (acc.meInfo || '').toLowerCase().includes(query);

        return nameMatch || phoneMatch || infoMatch;

      });

    }

    

    result.sort((a, b) => {

      const bucketA = getAccountSortBucket(a);

      const bucketB = getAccountSortBucket(b);

      if (bucketA !== bucketB) {

        return bucketA - bucketB;

      }

      return 0;

    });

    if (accountSortField === 'health') {

      result.sort((a, b) => {

        const bucketA = getAccountSortBucket(a);

        const bucketB = getAccountSortBucket(b);

        if (bucketA !== bucketB) {

          return bucketA - bucketB;

        }

        const scoreA = calculateHealthScore(a);

        const scoreB = calculateHealthScore(b);

        return accountSortDesc ? scoreB - scoreA : scoreA - scoreB;

      });

    }

    if (accountSortField === 'available') {

      result.sort((a, b) => {

        const bucketA = getAccountSortBucket(a);

        const bucketB = getAccountSortBucket(b);

        if (bucketA !== bucketB) return bucketA - bucketB;

        return 0;

      });

    }

    return result;

  };



  const handleToggleSelectAllAccounts = (filteredIds: string[]) => {
    const selectableIds = filteredIds.filter(id => {
      const account = backendAccounts.find(acc => acc.id === id);
      return account ? !isAccountLockedForManualOperation(account) : false;
    });

    if (selectableIds.length > 0 && selectedAccountIds.length === selectableIds.length) {

      setSelectedAccountIds([]);

    } else {

      setSelectedAccountIds(selectableIds);

    }

  };



  const handleBatchCheckAccountsStatus = async () => {

    if (selectedAccountIds.length === 0) return;

    setToastText(`正在批量检测 ${selectedAccountIds.length} 个账号的状态...`);

    

    await Promise.all(selectedAccountIds.map(async (accountId) => {

      const idx = backendAccounts.findIndex(acc => acc.id === accountId);

      if (idx !== -1) {

        await checkAccountLoginStatus(accountId, idx);

      }

    }));

    

    setToastText("所有选中账号状态检测完成！");

    setTimeout(() => setToastText(''), 2500);

  };



  const handleBatchClearAccountsSession = async () => {

    if (selectedAccountIds.length === 0) return;

    if (!confirm(`确定要清除选中的 ${selectedAccountIds.length} 个账号的 Session 吗？`)) {

      return;

    }

    

    setToastText(`正在批量清除 ${selectedAccountIds.length} 个账号的 Session...`);

    const backendUrl = BASE_URL;

    let successCount = 0;

    

    for (const accountId of selectedAccountIds) {

      try {

        const res = await fetch(`${backendUrl}/api/accounts/${accountId}/clear-session`, {

          method: 'POST'

        });

        if (res.ok) {

          successCount++;

        }

      } catch (err) {

        console.error(`Clear session failed for ${accountId}:`, err);

      }

    }

    

    setToastText(`成功清除 ${successCount} 个账号的 Session`);

    setTimeout(() => setToastText(''), 2500);

    setSelectedAccountIds([]);

    fetchBackendAccounts();

  };



  const handleBatchDeleteAccounts = async () => {

    if (selectedAccountIds.length === 0) return;

    if (!confirm(`确定要彻底删除选中的 ${selectedAccountIds.length} 个账号的配置和 Session 吗？此操作不可逆！`)) {

      return;

    }

    

    setToastText(`正在批量删除 ${selectedAccountIds.length} 个账号...`);

    const backendUrl = BASE_URL;

    let successCount = 0;

    

    for (const accountId of selectedAccountIds) {

      try {

        const res = await fetch(`${backendUrl}/api/accounts/${accountId}`, {

          method: 'DELETE'

        });

        if (res.ok) {

          successCount++;

        }

      } catch (err) {

        console.error(`Delete account failed for ${accountId}:`, err);

      }

    }

    

    setToastText(`成功彻底删除 ${successCount} 个账号`);

    setTimeout(() => setToastText(''), 2500);

    setSelectedAccountIds([]);

    fetchBackendAccounts();

  };



  const handleBatchUpdateProfiles = async (onlyAbout: boolean = false) => {

    if (batchEditTargetIds.length === 0) return;

    if (onlyAbout) {

      if (batchProfileAbout.trim().length > 70) {

        alert("个人简介最多支持 70 个字符！");

        return;

      }

    } else {

      if (!batchProfileLastName.trim()) {

        alert("固定姓氏不能为空");

        return;

      }

      if (!batchProfileVirtualModify) {

        if (!batchProfileFirstName.trim()) {

          alert("非虚拟修改时，名字不能为空");

          return;

        }

        if (!batchProfileUsernamePrefix.trim()) {

          alert("非虚拟修改时，用户名前缀不能为空");

          return;

        }

      }

    }

    

    setUpdatingBatchProfiles(true);

    setToastText(onlyAbout 

      ? `正在批量修改 ${batchEditTargetIds.length} 个账号的个人简介...`

      : `正在批量修改 ${batchEditTargetIds.length} 个账号的个人信息...`

    );

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/batch-update-profile`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          account_ids: batchEditTargetIds,

          only_about: onlyAbout,

          about: onlyAbout ? batchProfileAbout.trim() : undefined,

          last_name: onlyAbout ? undefined : batchProfileLastName.trim(),

          virtual_modify: onlyAbout ? undefined : batchProfileVirtualModify,

          custom_first_name: onlyAbout ? undefined : batchProfileFirstName.trim(),

          custom_username_prefix: onlyAbout ? undefined : batchProfileUsernamePrefix.trim()

        })

      });

      

      const data = await res.json();

      if (res.ok) {

        setToastText(onlyAbout

          ? `成功修改了 ${data.success_count} 个账号的个人简介`

          : `成功修改了 ${data.success_count} 个账号的个人信息`

        );

        if (data.failed_count > 0) {

          alert(`修改完成。成功: ${data.success_count}，失败: ${data.failed_count}。失败详情:\n` + 

            data.failed_details.map((f: any) => `${f.account_id}: ${f.error}`).join('\n')

          );

        }

        setTimeout(() => setToastText(''), 2500);

        setShowBatchProfileModal(false);

        setSelectedAccountIds([]);

        setBatchEditTargetIds([]);

        setIsBatchManagingAccounts(false);

        fetchBackendAccounts();

        if (isFromImportResult) {

          setImportBatchProfileCompleted(true);

          setShowImportResultModal(true);

        }

      } else {

        alert(`修改失败: ${data.detail || '未知原因'}`);

      }

    } catch (err: any) {

      alert(`修改异常: ${err.message}`);

    } finally {

      setUpdatingBatchProfiles(false);

    }

  };



  const handleUpdateProfileAvatar = async (accountId: string, file: File | null, libraryFilename?: string) => {

    setUpdatingAvatar(true);

    setToastText(`正在为账号 ${accountId} 更新头像...`);

    const backendUrl = BASE_URL;

    try {

      const formData = new FormData();

      if (libraryFilename) {

        formData.append('library_filename', libraryFilename);

      } else if (file) {

        formData.append('file', file);

      } else {

        alert("请先选择图片或从头像库中选择一张头像！");

        setUpdatingAvatar(false);

        return;

      }



      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/profile/avatar`, {

        method: 'POST',

        body: formData

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("头像更新成功！");

        setTimeout(() => setToastText(''), 2500);

        setSelectedAvatarFile(null);

        setSelectedLibraryAvatarName('');

        fetchBackendAccounts();

        checkAccountLoginStatus(accountId, backendAccounts.findIndex(a => a.id === accountId))

          .then(() => {

            const updated = backendAccounts.find(a => a.id === accountId);

            if (updated) setModalAccount(updated);

          });

      } else {

        alert(`头像修改失败: ${data.detail || '未知错误'}`);

      }

    } catch (err: any) {

      alert(`修改头像异常: ${err.message}`);

    } finally {

      setUpdatingAvatar(false);

    }

  };



  const handleBatchUpdateAvatars = async () => {

    if (batchEditTargetIds.length === 0) return;



    setUpdatingAvatar(true);

    setToastText(`正在为 ${batchEditTargetIds.length} 个账号批量修改头像...`);

    const backendUrl = BASE_URL;



    try {

      const formData = new FormData();

      formData.append('account_ids', JSON.stringify(batchEditTargetIds));

      

      if (batchAvatarSource === 'library') {

        if (selectedBatchLibraryAvatarNames.length === 0) {

          alert("请选择至少一张头像库图片！");

          setUpdatingAvatar(false);

          return;

        }

        formData.append('library_filenames', JSON.stringify(selectedBatchLibraryAvatarNames));

      } else {

        if (!batchAvatarFiles || batchAvatarFiles.length === 0) {

          alert("请选择本地头像图片！");

          setUpdatingAvatar(false);

          return;

        }

        for (let i = 0; i < batchAvatarFiles.length; i++) {

          formData.append('files', batchAvatarFiles[i]);

        }

      }



      const res = await fetch(`${backendUrl}/api/accounts/batch-update-avatar`, {

        method: 'POST',

        body: formData

      });

      

      const data = await res.json();

      if (res.ok) {

        setToastText(`成功修改了 ${data.success_count} 个账号的头像`);

        if (data.failed_count > 0) {

          alert(`修改完成。成功: ${data.success_count}，失败: ${data.failed_count}。失败详情:\n` + 

            data.failed_details.map((f: any) => `${f.account_id}: ${f.error}`).join('\n')

          );

        }

        setTimeout(() => setToastText(''), 2500);

        setShowBatchAvatarModal(false);

        setBatchAvatarFiles(null);

        setSelectedBatchLibraryAvatarNames([]);

        setSelectedAccountIds([]);

        setBatchEditTargetIds([]);

        setIsBatchManagingAccounts(false);

        fetchBackendAccounts();

        if (isFromImportResult) {

          setImportBatchAvatarCompleted(true);

          setShowImportResultModal(true);

        }

      } else {

        alert(`批量修改头像失败: ${data.detail || '未知错误'}`);

      }

    } catch (err: any) {

      alert(`批量修改头像异常: ${err.message}`);

    } finally {

      setUpdatingAvatar(false);

    }

  };



  const fetchCampaignTasks = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/campaign/tasks`);

      if (res.ok) {

        const data = await res.json();

        setCampaignTasks(data);

      }

    } catch (err) {

      console.error("加载广告发送任务失败:", err);

    }

  };



  const fetchCampaignFoldersGroups = async (accountId: string) => {

    if (!accountId) return;

    setLoadingCampaignFoldersGroups(true);

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/folders-groups`);

      if (res.ok) {

        const data = await res.json();

        setCampaignFoldersGroups(data);

        setSelectedCampaignFolderNames([]);

        setSelectedCampaignGroupIds([]);

      } else {

        const data = await res.json();

        alert(`获取文件夹和群组失败: ${data.detail || '未授权或网络异常'}`);

      }

    } catch (err: any) {

      console.error("获取文件夹/群组异常:", err);

      alert(`无法同步账号文件夹: ${err.message}`);

    } finally {

      setLoadingCampaignFoldersGroups(false);

    }

  };



  const fetchPredefinedAds = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/predefined-ads`);

      if (res.ok) {

        const data = await res.json();

        setAdTemplates(data);

      }

    } catch (err) {

      console.error("加载预设广告词失败:", err);

    }

  };



  const handleCreatePredefinedAd = async () => {

    if (!newTemplateDesc.trim() || !newTemplateContent.trim()) {

      alert("描述和内容均不能为空");

      return;

    }

    // 前端字数验证
    const contentLen = newTemplateContent.trim().length;
    if (newTemplateGtype.includes("短")) {
      if (contentLen >= 200) {
        alert(`字数不符：短广告内容长度必须在 200 字以下（当前 ${contentLen} 字）`);
        return;
      }
    } else if (newTemplateGtype.includes("长")) {
      if (contentLen < 200) {
        alert(`字数不符：长广告内容长度必须在 200 字及以上（当前 ${contentLen} 字）`);
        return;
      }
    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/predefined-ads`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          description: newTemplateDesc.trim(),

          content: newTemplateContent.trim(),

          group_type: newTemplateGtype

        })

      });

      if (res.ok) {

        setNewTemplateDesc('');

        setNewTemplateContent('');

        setNewTemplateGtype('英文短');

        setToastText("预设广告词保存成功");

        setTimeout(() => setToastText(''), 2000);

        fetchPredefinedAds();

      } else {

        const data = await res.json();

        alert(`保存失败: ${data.detail || '未知原因'}`);

      }

    } catch (err: any) {

      alert(`保存出错: ${err.message}`);

    }

  };

  const handleUpdatePredefinedAd = async () => {
    if (editingAdId === null) return;
    if (!newTemplateDesc.trim() || !newTemplateContent.trim()) {
      alert("描述和内容均不能为空");
      return;
    }

    // 前端字数验证
    const contentLen = newTemplateContent.trim().length;
    if (newTemplateGtype.includes("短")) {
      if (contentLen >= 200) {
        alert(`字数不符：短广告内容长度必须在 200 字以下（当前 ${contentLen} 字）`);
        return;
      }
    } else if (newTemplateGtype.includes("长")) {
      if (contentLen < 200) {
        alert(`字数不符：长广告内容长度必须在 200 字及以上（当前 ${contentLen} 字）`);
        return;
      }
    }

    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/predefined-ads/${editingAdId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: newTemplateDesc.trim(),
          content: newTemplateContent.trim(),
          group_type: newTemplateGtype
        })
      });
      if (res.ok) {
        setNewTemplateDesc('');
        setNewTemplateContent('');
        setEditingAdId(null);
        setNewTemplateGtype('英文短');
        setToastText("预设广告词修改成功");
        setTimeout(() => setToastText(''), 2000);
        fetchPredefinedAds();
      } else {
        const data = await res.json();
        alert(`修改失败: ${data.detail || '未知错误'}`);
      }
    } catch (err: any) {
      alert(`修改出错: ${err.message}`);
    }
  };



  const handleDeletePredefinedAd = async (id: number) => {

    if (!confirm("确认删除该条预设广告词？")) return;

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/predefined-ads/${id}`, {

        method: 'DELETE'

      });

      if (res.ok) {

        setToastText("预设广告词已删除");

        setTimeout(() => setToastText(''), 2000);

        fetchPredefinedAds();

      }

    } catch (err: any) {

      console.error("删除预设广告词失败:", err);

    }

  };



  const handleCreateCampaignTask = async () => {

    if (selectedCampaignAccountIds.length === 0) {

      alert("请选择执行任务的账号");

      return;

    }

    if (!campaignGroupInterval || campaignGroupInterval < 5) {

      alert("单个群发送间隔不能小于 5 秒，以防触发 Telegram 限制风控！");

      return;

    }

    if (!campaignRoundInterval || campaignRoundInterval < 1) {

      alert("请输入每轮循环间隔时间（至少为 1 分钟）！");

      return;

    }

    const handwrittenAds = campaignMessage
      .split('====')
      .map((x: string) => x.trim())
      .filter((x: string) => x.length > 0);

    const selectedPredefinedAds = (campaignStrategyEnabled && selectedAdTemplateIds.length === 0 && handwrittenAds.length === 0)
      ? adTemplates.map((ad: any) => ad.content.trim()).filter((x: string) => x.length > 0)
      : adTemplates
          .filter((ad: any) => selectedAdTemplateIds.includes(ad.id))
          .map((ad: any) => ad.content.trim())
          .filter((x: string) => x.length > 0);

    const allAdsPool = [...selectedPredefinedAds, ...handwrittenAds];

    if (!campaignStrategyEnabled && allAdsPool.length === 0) {
      alert("请输入要发送的广告内容，或勾选常用广告语！");
      return;
    }

    const payloadMessage = JSON.stringify(allAdsPool);

    const backendUrl = BASE_URL;



    let resolvedGroups: Array<{ chat_id: number; title: string; username: string }> = [];



    if (campaignInputMode === 'library') {

      if (selectedCampaignLibraryGroupIds.length === 0) {

        alert("请选择至少一个系统群组库里的目标群组！");

        return;

      }

      groups
        .filter(g => selectedCampaignLibraryGroupIds.includes(g.id) && g.enabled)
        .forEach(g => {
          const username = g.username ? (g.username.startsWith('@') ? g.username : `@${g.username}`) : g.id;
          const parsedId = Number(g.id);
          resolvedGroups.push({
            chat_id: Number.isFinite(parsedId) ? parsedId : 0,
            title: g.title || username,
            username
          });
        });

      if (resolvedGroups.length === 0) {

        alert("未解析到可用群组，请确认选择的群组处于启用状态！");

        return;

      }

    } else if (selectedCampaignAccountIds.length === 1 && campaignInputMode === 'folders') {

      if (selectedCampaignGroupIds.length === 0) {

        alert("请选择至少一个目标群组进行发送！");

        return;

      }

      Object.values(campaignFoldersGroups).forEach(groupList => {

        groupList.forEach(g => {

          if (selectedCampaignGroupIds.includes(g.chat_id) && !resolvedGroups.some(rg => rg.chat_id === g.chat_id)) {

            resolvedGroups.push(g);

          }

        });

      });

    } else {

      if (!campaignGroupListText.trim()) {

        alert("请输入群组列表！");

        return;

      }

      const lines = campaignGroupListText.split('\n');

      lines.forEach(line => {

        const cleaned = line.trim();

        if (cleaned) {

          resolvedGroups.push({

            chat_id: 0,

            title: cleaned,

            username: cleaned

          });

        }

      });

      if (resolvedGroups.length === 0) {

        alert("未解析到有效的群组，请每行输入一个群组链接或用户名");

        return;

      }

    }



    try {

      const res = await fetch(`${backendUrl}/api/campaign/tasks`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          account_id: selectedCampaignAccountIds[0],

          account_ids: selectedCampaignAccountIds,

          max_cycles: campaignMaxCycles,

          round_interval_minutes: campaignRoundInterval,

          group_interval_seconds: campaignGroupInterval,

          is_safety: campaignIsSafety,

          multi_account_safety_enabled: campaignMultiAccountSafety && selectedCampaignAccountIds.length > 1,

          strategy_enabled: campaignStrategyEnabled,

          message: payloadMessage,

          target_groups: resolvedGroups

        })

      });

      if (res.ok) {

        setToastText(`已成功启动 ${selectedCampaignAccountIds.length} 个账号的随机调度群发任务`);

        setTimeout(() => setToastText(''), 2500);

        setShowCreateCampaignModal(false);

        fetchCampaignTasks();

      } else {

        const data = await res.json();

        alert(`启动群发任务失败：${data.detail || '请检查账号状态或后端日志'}`);

      }

    } catch (err: any) {

      alert(`网络错误: ${err.message}`);

    }

  };



  const handleStopCampaignTask = async (taskIdOrIds: string | string[]) => {

    const backendUrl = BASE_URL;

    try {

      const taskIds = Array.isArray(taskIdOrIds) ? taskIdOrIds : [taskIdOrIds];

      let success = false;

      for (const tid of taskIds) {

        const res = await fetch(`${backendUrl}/api/campaign/tasks/${tid}/stop`, {

          method: 'POST'

        });

        if (res.ok) {

          success = true;

        }

      }

      if (success) {

        setToastText("任务已成功停止！");

        setTimeout(() => setToastText(''), 2000);

        fetchCampaignTasks();

      }

    } catch (err) {

      console.error(err);

    }

  };



  const handleStopAllCampaignTasks = () => {

    setCustomConfirm({

      title: "停止所有任务",

      message: "确定要停止所有当前运行中的广告发送任务吗？",

      confirmText: "停止所有",

      cancelText: "取消",

      type: "danger",

      onConfirm: async () => {

        setCustomConfirm(null);

        const backendUrl = BASE_URL;

        try {

          const res = await fetch(`${backendUrl}/api/campaign/stop-all`, {

            method: 'POST'

          });

          if (res.ok) {

            setToastText("已停止所有轰炸任务！");

            setTimeout(() => setToastText(''), 2000);

            fetchCampaignTasks();

          }

        } catch (err) {

          console.error(err);

        }

      },

      onCancel: () => setCustomConfirm(null)

    });

  };



  const fetchCampaignTaskLogs = async (taskIdOrIds: string | string[]) => {

    const backendUrl = BASE_URL;

    try {

      const taskIds = Array.isArray(taskIdOrIds) ? taskIdOrIds : [taskIdOrIds];

      const allLogs = [];

      for (const tid of taskIds) {

        const res = await fetch(`${backendUrl}/api/campaign/tasks/${tid}/logs`);

        if (res.ok) {

          const data = await res.json();

          const taskObj = campaignTasks.find(t => t.id === tid);

          const phone = taskObj ? taskObj.phone : '';

          const tagged = data.map((log: any) => ({ ...log, phone: log.phone || phone }));

          allLogs.push(...tagged);

        }

      }

      allLogs.sort((a, b) => b.timestamp.localeCompare(a.timestamp));

      setActiveCampaignTaskLogs(allLogs);

    } catch (err) {

      console.error(err);

    }

  };



  const fetchCampaignLastParams = async (accountId: string) => {

    if (!accountId) return;

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/campaign/accounts/${accountId}/last-params`);

      if (res.ok) {

        const data = await res.json();

        if (data.status !== 'none') {

          setCustomConfirm({

            title: "加载上次配置",

            message: "检测到此账号上一次执行过群发广告任务，是否加载上次配置的所有群组和发送参数？",

            confirmText: "加载",

            cancelText: "取消",

            type: "info",

            onConfirm: () => {

              setCampaignMaxCycles(data.max_cycles);

              setCampaignRoundInterval(data.round_interval_minutes);

              setCampaignGroupInterval(data.group_interval_seconds);

              setCampaignIsSafety(data.is_safety);

              setCampaignMultiAccountSafety(Boolean(data.multi_account_safety_enabled));

              setCampaignMessage(data.message);

              

              if (data.target_groups && data.target_groups.length > 0) {

                const lastGroupIds = data.target_groups.map((g: any) => g.chat_id);

                setSelectedCampaignGroupIds(lastGroupIds);

              }

              setCustomConfirm(null);

            },

            onCancel: () => setCustomConfirm(null)

          });

        }

      }

    } catch (err) {

      console.error(err);

    }

  };



  const fetchAvatarLibrary = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/avatar-library`);

      if (res.ok) {

        const data = await res.json();

        setAvatarLibrary(data);

      }

    } catch (err) {

      console.error("加载头像库失败:", err);

    }

  };



  const handleUploadToAvatarLibrary = async (files: FileList) => {

    setUploadingToLibrary(true);

    const backendUrl = BASE_URL;

    try {

      const formData = new FormData();

      let hasOversized = false;

      for (let i = 0; i < files.length; i++) {

        if (files[i].size > 10 * 1024 * 1024) {

          hasOversized = true;

          continue;

        }

        formData.append('files', files[i]);

      }

      if (hasOversized) {

        alert("部分图片超过 10MB，已被自动过滤。仅支持 10MB 以下图片！");

      }

      

      const res = await fetch(`${backendUrl}/api/avatar-library`, {

        method: 'POST',

        body: formData

      });

      const data = await res.json();

      if (res.ok) {

        setToastText(`成功上传了 ${data.files.length} 张头像到库中`);

        setTimeout(() => setToastText(''), 2500);

        fetchAvatarLibrary();

      } else {

        alert(`上传失败: ${data.detail || '未知错误'}`);

      }

    } catch (err: any) {

      alert(`上传到头像库异常: ${err.message}`);

    } finally {

      setUploadingToLibrary(false);

    }

  };



  const handleDeleteFromAvatarLibrary = async (filename: string) => {

    if (!confirm(`确定要从头像库中彻底删除头像 "${filename}" 吗？`)) return;

    

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/avatar-library/${encodeURIComponent(filename)}`, {

        method: 'DELETE'

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("删除成功");

        setTimeout(() => setToastText(''), 1500);

        fetchAvatarLibrary();

        if (selectedLibraryAvatarName === filename) {

          setSelectedLibraryAvatarName('');

        }

        setSelectedBatchLibraryAvatarNames(prev => prev.filter(n => n !== filename));

      } else {

        alert(`删除失败: ${data.detail || '未知错误'}`);

      }

    } catch (err: any) {

      alert(`删除异常: ${err.message}`);

    }

  };



  const handleRenameInAvatarLibrary = async (oldName: string, newName: string) => {

    if (!newName.trim() || oldName === newName.trim()) return;

    

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/avatar-library/rename`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({ old_name: oldName, new_name: newName })

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("重命名成功");

        setTimeout(() => setToastText(''), 1500);

        fetchAvatarLibrary();

        if (selectedLibraryAvatarName === oldName) {

          setSelectedLibraryAvatarName(data.filename);

        }

        setSelectedBatchLibraryAvatarNames(prev => prev.map(n => n === oldName ? data.filename : n));

      } else {

        alert(`重命名失败: ${data.detail || '未知错误'}`);

      }

    } catch (err: any) {

      alert(`重命名异常: ${err.message}`);

    }

  };



  const handleCloseBatchProfileModal = () => {

    setShowBatchProfileModal(false);

    if (isFromImportResult) {

      setShowImportResultModal(true);

    }

  };



  const handleCloseBatchAvatarModal = () => {

    setShowBatchAvatarModal(false);

    setBatchAvatarFiles(null);

    setSelectedBatchLibraryAvatarNames([]);

    if (isFromImportResult) {

      setShowImportResultModal(true);

    }

  };



  const postLoginLog = async (

    phone: string,

    apiLink: string | null,

    originalPassword: string | null,

    currentPassword: string | null,

    loginType: 'import' | 'manual',

    status: 'success' | 'failed',

    errorDetail?: string | null

  ) => {

    const backendUrl = BASE_URL;

    try {

      await fetch(`${backendUrl}/api/login/logs`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          phone: phone,

          api_link: apiLink || null,

          original_password: originalPassword || null,

          current_password: currentPassword || null,

          login_type: loginType,

          status: status,

          error_detail: errorDetail || null

        })

      });

    } catch (e) {

      console.error("Failed to post login log:", e);

    }

  };



  const fetchLoginLogs = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/login/logs`);

      if (res.ok) {

        const data = await res.json();

        setLoginLogs(data);

      }

    } catch (err) {

      console.error("Failed to fetch login logs:", err);

    }

  };



  const handleClearLoginLogs = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/login/logs`, {

        method: 'DELETE'

      });

      if (res.ok) {

        setToastText("登录历史记录已清空");

        setTimeout(() => setToastText(''), 1500);

        fetchLoginLogs();

      }

    } catch (err: any) {

      alert(`清空历史记录失败: ${err.message}`);

    }

  };



  const handleCloseBatch2faModal = () => {

    setShowBatch2faModal(false);

    setBatch2faCurrentPassword('');

    setBatch2faCustomNewPassword('');

    setBatch2faHint('');

    setBatch2faNewPasswordMode('same');

    if (isFromImportResult) {

      setShowImportResultModal(true);

    }

  };



  // 2FA Single Account States & Handler

  const [edit2faCurrentPassword, setEdit2faCurrentPassword] = useState<string>('');

  const [edit2faNewPassword, setEdit2faNewPassword] = useState<string>('');

  const [edit2faHint, setEdit2faHint] = useState<string>('');

  const [updating2fa, setUpdating2fa] = useState<boolean>(false);



  const fetchAccountDevices = async (accountId: string) => {

    setLoadingDevices(true);

    setDevicesError('');

    setAccountDevices([]);

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/devices`);

      if (res.ok) {

        const data = await res.json();

        setAccountDevices(data.devices || []);

      } else {

        const errData = await res.json();

        console.error("Failed to fetch devices:", errData.detail);

        setDevicesError(errData.detail || '获取设备列表失败');

      }

    } catch (err: any) {

      console.error("Failed to fetch devices:", err);

      setDevicesError(err.message || '网络连接或电报通信异常');

    } finally {

      setLoadingDevices(false);

    }

  };



  const handleKickDevice = async (accountId: string, hash: string) => {

    if (!confirm("确定要将该设备踢下线（终止其登录会话）吗？")) {

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/devices/kick`, {

        method: 'POST',

        headers: {

          'Content-Type': 'application/json'

        },

        body: JSON.stringify({ hash })

      });

      if (res.ok) {

        setToastText('设备已成功踢下线');

        setTimeout(() => setToastText(''), 2500);

        // Refresh device list

        fetchAccountDevices(accountId);

      } else {

        const errData = await res.json();

        alert(`踢下线失败: ${errData.detail}`);

      }

    } catch (err: any) {

      alert(`踢下线失败: ${err.message}`);

    }

  };



  const handleUpdateAccount2fa = async (accountId: string) => {

    if (!edit2faNewPassword.trim()) {

      alert("新两步验证密码不能为空");

      return;

    }

    setUpdating2fa(true);

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/profile/2fa`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          current_password: edit2faCurrentPassword.trim(),

          new_password: edit2faNewPassword.trim(),

          hint: edit2faHint.trim()

        })

      });

      const data = await res.json();

      if (res.ok) {

        alert(data.message || "两步验证密码修改成功！");

        setEdit2faCurrentPassword('');

        setEdit2faNewPassword('');

        setEdit2faHint('');

        fetchBackendAccounts();

      } else {

        alert(`修改失败: ${data.detail || '原因未知'}`);

      }

    } catch (err: any) {

      alert(`网络异常: ${err.message}`);

    } finally {

      setUpdating2fa(false);

    }

  };





  // 2FA Batch Accounts States & Handler

  const [showBatch2faModal, setShowBatch2faModal] = useState<boolean>(false);

  const [batch2faCurrentPassword, setBatch2faCurrentPassword] = useState<string>('');

  const [batch2faNewPasswordMode, setBatch2faNewPasswordMode] = useState<'same' | 'auto'>('same');

  const [batch2faCustomNewPassword, setBatch2faCustomNewPassword] = useState<string>('');

  const [batch2faHint, setBatch2faHint] = useState<string>('');

  const [updatingBatch2fa, setUpdatingBatch2fa] = useState<boolean>(false);



  const handleBatchUpdate2fa = async () => {

    if (batch2faNewPasswordMode === 'same' && !batch2faCustomNewPassword.trim()) {

      alert("请输入新的两步验证密码");

      return;

    }

    setUpdatingBatch2fa(true);

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/batch-update-2fa`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          account_ids: batchEditTargetIds,

          current_password: batch2faCurrentPassword.trim(),

          new_password_mode: batch2faNewPasswordMode,

          custom_new_password: batch2faCustomNewPassword.trim(),

          hint: batch2faHint.trim()

        })

      });

      const data = await res.json();

      if (res.ok) {

        let msg = `两步验证修改成功！\n成功: ${data.success_count} 个，失败: ${data.failed_count} 个。\n\n`;

        if (data.success_details && data.success_details.length > 0) {

          msg += "已修改账号与新密码对照表：\n";

          data.success_details.forEach((item: any) => {

            msg += `- 账号 ${item.account_id}: ${item.new_password}\n`;

          });

        }

        if (data.failed_details && data.failed_details.length > 0) {

          msg += "\n失败详情：\n";

          data.failed_details.forEach((item: any) => {

            msg += `- 账号 ${item.account_id}: ${item.error}\n`;

          });

        }

        alert(msg);

        

        // Reset states

        setBatch2faCurrentPassword('');

        setBatch2faCustomNewPassword('');

        setBatch2faHint('');

        setBatch2faNewPasswordMode('same');

        setShowBatch2faModal(false);

        setSelectedAccountIds([]);

        setBatchEditTargetIds([]);

        setIsBatchManagingAccounts(false);

        fetchBackendAccounts();

      } else {

        alert(`修改失败: ${data.detail || '原因未知'}`);

      }

    } catch (err: any) {

      alert(`网络异常: ${err.message}`);

    } finally {

      setUpdatingBatch2fa(false);

    }

  };



  const [showManageModal, setShowManageModal] = useState<boolean>(false);

  const [modalAccount, setModalAccount] = useState<BackendAccount | null>(null);

  const [showHealthDetailsModal, setShowHealthDetailsModal] = useState<boolean>(false);

  const [healthDetailsAccount, setHealthDetailsAccount] = useState<BackendAccount | null>(null);

  const [checkingHealth, setCheckingHealth] = useState<boolean>(false);

  const [accountDevices, setAccountDevices] = useState<any[]>([]);

  const [loadingDevices, setLoadingDevices] = useState<boolean>(false);

  const [devicesError, setDevicesError] = useState<string>('');

  const [editFirstName, setEditFirstName] = useState<string>('');

  const [editLastName, setEditLastName] = useState<string>('');

  const [editUsername, setEditUsername] = useState<string>('');

  const [newFolderTitle, setNewFolderTitle] = useState<string>('广告');

  const [folderCategories, setFolderCategories] = useState<string[]>(['groups', 'broadcasts']);

  const [capturedCodes, setCapturedCodes] = useState<any[]>([]);
  const [loginConnectionLogs, setLoginConnectionLogs] = useState<string[]>([]);
  const loginConnectionLogsRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (loginConnectionLogsRef.current) {
      loginConnectionLogsRef.current.scrollTop = loginConnectionLogsRef.current.scrollHeight;
    }
  }, [loginConnectionLogs]);
  const [capturedRawMessages, setCapturedRawMessages] = useState<any[]>([]);
  const [loginInfoError, setLoginInfoError] = useState<string | null>(null);
  const [loginInfoConnecting, setLoginInfoConnecting] = useState<boolean>(false);

  const [localPageId, setLocalPageId] = useState<string>('');

  const [local2fa, setLocal2fa] = useState<string>('');

  const [showLoginInfoModal, setShowLoginInfoModal] = useState<boolean>(false);

  const [loginInfoAccount, setLoginInfoAccount] = useState<BackendAccount | null>(null);

  const [loginInfoModalOpenTime, setLoginInfoModalOpenTime] = useState<number>(0);

  const [showLoginInfo2faText, setShowLoginInfo2faText] = useState<boolean>(false);



  useEffect(() => {

    if (showLoginInfoModal && loginInfoAccount) {

      const fetchCapturedCodes = async (accountId: string) => {

        const backendUrl = BASE_URL;

        try {

          const res = await fetch(`${backendUrl}/api/accounts/${accountId}/login-code`);

          if (res.ok) {

            const data = await res.json();

            if (data.status === 'success') {
              setCapturedRawMessages(data.raw_messages || []);
              setLoginConnectionLogs(data.logs || []);
              setLoginInfoError(data.error || null);
              setLoginInfoConnecting(data.is_connecting || false);
            }

          }

        } catch (err) {

          console.error("Error fetching captured codes:", err);

        }

      };

      

      fetchCapturedCodes(loginInfoAccount.id);

      const interval = setInterval(() => {

        fetchCapturedCodes(loginInfoAccount.id);

      }, 3000);

      

      return () => {

        clearInterval(interval);

        setCapturedCodes([]);
        setCapturedRawMessages([]);
        setLoginConnectionLogs([]);

      };

    }

  }, [showLoginInfoModal, loginInfoAccount, loginInfoModalOpenTime]);



  const handleOpenLoginInfoModal = (acc: BackendAccount) => {

    setLoginInfoAccount(acc);

    setLoginInfoModalOpenTime(Date.now() / 1000);

    setLocalPageId(acc.config?.page_id || '');

    setLocal2fa(acc.config?.pass2fa || '');

    setCapturedCodes([]);
    setLoginConnectionLogs([]);
    setCapturedRawMessages([]);

    setShowLoginInfo2faText(false);

    setShowLoginInfoModal(true);

  };



  const handleOpenManageModal = (acc: BackendAccount) => {

    setModalAccount(acc);

    setShowManageModal(true);

    let first = '';

    let last = '';

    let user = '';

    if (acc.meInfo) {

      const idIdx = acc.meInfo.indexOf('(ID:');

      let cleanInfo = idIdx !== -1 ? acc.meInfo.substring(0, idIdx).trim() : acc.meInfo;

      const userMatch = cleanInfo.match(/@(\w+)/);

      if (userMatch) {

        user = userMatch[1];

        cleanInfo = cleanInfo.replace(`@${user}`, '').trim();

      }

      const nameParts = cleanInfo.split(/\s+/);

      if (nameParts.length > 0) {

        first = nameParts[0];

        if (nameParts.length > 1) {

          last = nameParts.slice(1).join(' ');

        }

      }

    }

    setEditFirstName(first);

    setEditLastName(last);

    setEditUsername(user);

    setNewFolderTitle('广告');

    setFolderCategories(['groups', 'broadcasts']);

    setLocalPageId(acc.config?.page_id || '');

    setLocal2fa(acc.config?.pass2fa || '');

    fetchAccountDevices(acc.id);

  };



  const handleUpdateLocalCredentials = async (accountId: string) => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/local-credentials`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          page_id: localPageId.trim() || null,

          pass2fa: local2fa.trim() || null

        })

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("凭证保存成功");

        setTimeout(() => setToastText(''), 2000);

        if (modalAccount) {

          setModalAccount({

            ...modalAccount,

            config: {

              ...modalAccount.config,

              page_id: localPageId.trim() || undefined,

              pass2fa: local2fa.trim() || undefined

            }

          });

        }

        if (loginInfoAccount) {

          setLoginInfoAccount({

            ...loginInfoAccount,

            config: {

              ...loginInfoAccount.config,

              page_id: localPageId.trim() || undefined,

              pass2fa: local2fa.trim() || undefined

            }

          });

        }

        fetchBackendAccounts();

      } else {

        alert(`凭证保存失败: ${data.detail || '原因未知'}`);

      }

    } catch (err: any) {

      alert(`网络异常: ${err.message}`);

    }

  };



  const handleUpdateProfileName = async (accountId: string) => {

    if (!editFirstName.trim()) {

      alert("名字不能为空");

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/profile/name`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          first_name: editFirstName.trim(),

          last_name: editLastName.trim()

        })

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("姓名修改成功");

        setTimeout(() => setToastText(''), 2000);

        fetchBackendAccounts();

      } else {

        alert(`修改姓名失败: ${data.detail}`);

      }

    } catch (err: any) {

      alert(`修改姓名异常: ${err.message}`);

    }

  };



  const handleUpdateProfileUsername = async (accountId: string) => {

    const cleanUsername = editUsername.trim().replace("@", "");

    if (!cleanUsername) {

      alert("用户名不能为空");

      return;

    }

    if (cleanUsername.length < 5 || cleanUsername.length > 32) {

      alert("用户名长度必须在 5 到 32 个字符之间");

      return;

    }

    if (!/^[a-zA-Z0-9_]+$/.test(cleanUsername)) {

      alert("用户名只能包含字母、数字和下划线");

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/profile/username`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          username: cleanUsername

        })

      });

      const data = await res.json();

      if (res.ok) {

        setToastText("用户名修改成功");

        setTimeout(() => setToastText(''), 2000);

        fetchBackendAccounts();

      } else {

        alert(`修改用户名失败: ${data.detail}`);

      }

    } catch (err: any) {

      alert(`修改用户名异常: ${err.message}`);

    }

  };



  const handleCreateChatFolder = async (accountId: string) => {

    if (!newFolderTitle.trim()) {

      alert("文件夹名称不能为空");

      return;

    }

    if (folderCategories.length === 0) {

      alert("请选择至少一个聊天类别");

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/accounts/${accountId}/folders/create`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          title: newFolderTitle.trim(),

          categories: folderCategories

        })

      });

      const data = await res.json();

      if (res.ok) {

        setToastText(`文件夹 "${newFolderTitle}" 创建成功`);

        setTimeout(() => setToastText(''), 2000);

        fetchBackendAccounts();

      } else {

        alert(`创建文件夹失败: ${data.detail}`);

      }

    } catch (err: any) {

      alert(`创建文件夹异常: ${err.message}`);

    }

  };

  

  const handleStartJoinTask = async () => {

    if (selectedJoinAccounts.length === 0) {

      alert("请选择至少一个执行账号！");

      return;

    }

    const parsedLinks = joinLinks.split('\n').map(l => l.trim()).filter(l => l !== '');

    if (parsedLinks.length === 0) {

      alert("请输入有效的入群链接，每行一个！");

      return;

    }

    if (moveJoinToFolder && !joinFolderByType && !joinTargetFolderName.trim()) {

      alert("请选择自动分类或填写手动文件夹名称！");

      return;

    }



    if (joinStrategy === 'fixed' && (!joinDelay || joinDelay < 30)) {

      alert("根据电报官方防封限制规则，时间间隔不能小于 30 秒，否则极易导致批量风控封号！");

      return;

    }

    if (joinStrategy === 'safety') {

      if (!joinSafetyMinutes || !joinSafetyGroups) {

        alert("请输入完整的安全频率分钟数和最大群组数量！");

        return;

      }

      const avg = (Number(joinSafetyMinutes) * 60) / Number(joinSafetyGroups);

      if (avg < 30) {

        alert(`所选安全频率（${joinSafetyMinutes}分钟加入${joinSafetyGroups}个）平均间隔为 ${avg.toFixed(1)} 秒，小于安全红线 30 秒！已被拒绝。`);

        return;

      }

    }



    setJoinRunning(true);

    setJoinTaskId(''); // Clear old task ID to prevent race condition polling of the previous task

    setSelectedHistoryTask(null); // Clear selected history task to ensure the live execution board is shown

    setJoinResults([]);

    setJoinLogs(["正在准备创建后台入群任务..."]);

    setJoinProgress({ current: 0, total: 0 });



    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/groups/join-task`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          account_ids: selectedJoinAccounts,

          links: parsedLinks,

          mode: joinMode,

          strategy: joinStrategy,

          fixed_delay: joinDelay,

          safety_groups: joinSafetyGroups,

          safety_minutes: joinSafetyMinutes,

          move_to_folder: moveJoinToFolder,

          folder_by_type: moveJoinToFolder ? joinFolderByType : false,

          target_folder_name: moveJoinToFolder && !joinFolderByType ? joinTargetFolderName.trim() : ''

        })

      });

      const data = await res.json();

      if (res.ok) {

        setJoinTaskId(data.task_id);

        setToastText("自动入群任务启动成功！");

        setTimeout(() => setToastText(''), 2000);

      } else {

        alert(`任务启动失败: ${data.detail || '原因未知'}`);

        setJoinRunning(false);

      }

    } catch (err: any) {

      alert(`网络异常: ${err.message}`);

      setJoinRunning(false);

    }

  };



  const handleStopJoinTask = async () => {

    if (!joinTaskId) return;

    const backendUrl = BASE_URL;

    try {

      await fetch(`${backendUrl}/api/groups/join-task/stop`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({ task_id: joinTaskId })

      });

      setToastText("正在停止任务...");

      setTimeout(() => setToastText(''), 2000);

    } catch (err) {

      console.error("Failed to stop join task:", err);

    }

  };



  const fetchGroups = async () => {

    const backendUrl = BASE_URL;

    try {

      const res = await fetch(`${backendUrl}/api/groups`);

      if (res.ok) {

        const data = await res.json();

        setGroups(data);

      }

    } catch (err) {

      console.error("Failed to fetch groups:", err);

    }

  };



  const handleToggleGroup = async (groupId: string, enabled: boolean) => {

    const backendUrl = BASE_URL;

    try {

      setGroups(prev => prev.map(g => g.id === groupId ? { ...g, enabled } : g));

      const res = await fetch(`${backendUrl}/api/groups/toggle`, {

        method: 'POST',

        headers: {

          'Content-Type': 'application/json',

        },

        body: JSON.stringify({ id: groupId, enabled }),

      });

      if (!res.ok) {

        fetchGroups();

      }

    } catch (err) {

      console.error("Failed to toggle group:", err);

      fetchGroups();

    }

  };



  const handleDeleteGroup = async (groupId: string) => {

    if (!confirm('确定要删除该群组吗？')) {

      return;

    }

    const backendUrl = BASE_URL;

    try {

      setGroups(prev => prev.filter(g => g.id !== groupId));

      const res = await fetch(`${backendUrl}/api/groups/${groupId}`, {

        method: 'DELETE',

      });

      if (!res.ok) {

        fetchGroups();

      } else {

        setToastText('群组删除成功');

        setTimeout(() => setToastText(''), 2000);

      }

    } catch (err) {

      console.error("Failed to delete group:", err);

      fetchGroups();

    }

  };

  const formatTime = (dateStr?: string) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return '';
      const pad = (n: number) => n.toString().padStart(2, '0');
      return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    } catch (e) {
      return '';
    }
  };

  const fetchGroupCategories = async () => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/group-categories`);
      if (res.ok) {
        const data = await res.json();
        setGroupCategories(data);
        if (data.length > 0) {
          if (!data.some((c: any) => c.name === newGroupCategory)) {
            setNewGroupCategory(data[0].name);
          }
          if (!data.some((c: any) => c.name === categoryToAssignScraped)) {
            setCategoryToAssignScraped(data[0].name);
          }
          if (!data.some((c: any) => c.name === selectedImportCategory)) {
            setSelectedImportCategory(data[0].name);
          }
        }
      }
    } catch (err) {
      console.error("Failed to fetch group categories:", err);
    }
  };

  const getGroupQualityScore = (group: Group) => {
    const rawScore = group.quality_score ?? group.activity_score ?? 0;
    const score = Number(rawScore);
    return Number.isFinite(score) ? score : 0;
  };

  const getGroupScoreBadgeClass = (score: number) => {
    if (score >= 80) return 'bg-emerald-50 text-emerald-700 border-emerald-100';
    if (score >= 60) return 'bg-blue-50 text-blue-700 border-blue-100';
    if (score >= 40) return 'bg-amber-50 text-amber-700 border-amber-100';
    if (score > 0) return 'bg-rose-50 text-rose-700 border-rose-100';
    return 'bg-slate-100 text-slate-400 border-slate-200';
  };

  const getGroupTelegramLink = (group: Group) => {
    const username = (group.username || '').replace(/^@+/, '').trim();
    return username ? `https://t.me/${username}` : '';
  };

  const sortedGroups = [...groups].sort((a, b) => {
    if (groupSortField === 'quality') {
      const diff = getGroupQualityScore(a) - getGroupQualityScore(b);
      return groupSortOrder === 'asc' ? diff : -diff;
    }
    if (groupSortField === 'members') {
      const diff = Number(a.memberCount || 0) - Number(b.memberCount || 0);
      return groupSortOrder === 'asc' ? diff : -diff;
    }
    if (groupSortField === 'status') {
      const diff = Number(a.enabled) - Number(b.enabled);
      return groupSortOrder === 'asc' ? diff : -diff;
    }
    if (groupSortField === 'title') {
      const diff = (a.title || '').localeCompare(b.title || '', 'zh-Hans-CN');
      return groupSortOrder === 'asc' ? diff : -diff;
    }
    return 0;
  });

  const buildGroupSyncSummary = (syncData: any, statusData: any): GroupSyncSummary => {
    const syncedGroups: Group[] = Array.isArray(statusData?.groups) ? statusData.groups : [];
    const memberRanges: Record<string, number> = {
      '10,000+': 0,
      '5,000-9,999': 0,
      '1,000-4,999': 0,
      '100-999': 0,
      '1-99': 0,
      '未知/0': 0,
    };
    const scoreRanges: Record<string, number> = {
      '80-100 高质量': 0,
      '60-79 可用': 0,
      '40-59 一般': 0,
      '1-39 低质量': 0,
      '0 疑似死群': 0,
      '未检测': 0,
    };
    let hasScore = false;

    syncedGroups.forEach((group: any) => {
      const members = Number(group.memberCount || 0);
      if (members >= 10000) memberRanges['10,000+'] += 1;
      else if (members >= 5000) memberRanges['5,000-9,999'] += 1;
      else if (members >= 1000) memberRanges['1,000-4,999'] += 1;
      else if (members >= 100) memberRanges['100-999'] += 1;
      else if (members > 0) memberRanges['1-99'] += 1;
      else memberRanges['未知/0'] += 1;

      const rawScore = group.qualityScore ?? group.quality_score ?? group.activityScore ?? group.activity_score;
      if (rawScore === undefined || rawScore === null || rawScore === '') {
        scoreRanges['未检测'] += 1;
        return;
      }
      hasScore = true;
      const score = Number(rawScore);
      if (!Number.isFinite(score)) {
        scoreRanges['未检测'] += 1;
      } else if (score >= 80) scoreRanges['80-100 高质量'] += 1;
      else if (score >= 60) scoreRanges['60-79 可用'] += 1;
      else if (score >= 40) scoreRanges['40-59 一般'] += 1;
      else if (score > 0) scoreRanges['1-39 低质量'] += 1;
      else scoreRanges['0 疑似死群'] += 1;
    });

    return {
      syncedCount: Number(syncData?.synced_count || 0),
      addedCount: Number(syncData?.added_count || 0),
      skippedCount: Number(syncData?.skipped_count || 0),
      updatedCount: Number(statusData?.updated_count || 0),
      disabledCount: Number(statusData?.disabled_count || 0),
      invalidCount: Array.isArray(statusData?.invalid_groups) ? statusData.invalid_groups.length : 0,
      totalGroups: syncedGroups.length,
      enabledCount: syncedGroups.filter((group: any) => group.enabled).length,
      disabledTotalCount: syncedGroups.filter((group: any) => !group.enabled).length,
      memberRanges,
      scoreRanges,
      hasScore,
      errors: Array.isArray(syncData?.errors) ? syncData.errors : [],
      invalidGroups: Array.isArray(statusData?.invalid_groups) ? statusData.invalid_groups : [],
    };
  };

  const handleRunGroupSyncWithLogs = async () => {
    const startedAt = new Date();
    const pushLog = (message: string) => {
      const now = new Date();
      const stamp = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
      setGroupSyncExecutionLogs(prev => [...prev, `[${stamp}] ${message}`]);
    };

    setGroupSyncSummary(null);
    setGroupSyncExecutionLogs([]);
    setShowGroupSyncExecutionModal(true);
    setGroupSyncRunning(true);
    pushLog("开始执行群组同步。");

    const token = localStorage.getItem('rosepay_auth_token') || sessionStorage.getItem('rosepay_auth_token');
    if (!token) {
      pushLog("同步失败：登录状态已失效，请重新登录。");
      setToastText("❌ 登录状态已失效，请重新登录");
      setGroupSyncRunning(false);
      setTimeout(() => setToastText(''), 4000);
      return;
    }

    const streamUrl = `${BASE_URL}/api/groups/sync-stream?token=${encodeURIComponent(token)}`;
    const sourceRef: { current: EventSource | null } = { current: null };

    try {
      await new Promise<void>((resolve, reject) => {
        const source = new EventSource(streamUrl);
        sourceRef.current = source;

        source.addEventListener('log', (event: MessageEvent) => {
          try {
            const data = JSON.parse(event.data);
            if (data?.message) {
              pushLog(data.message);
            }
          } catch {
            pushLog(event.data);
          }
        });

        source.addEventListener('done', (event: MessageEvent) => {
          try {
            const data = JSON.parse(event.data);
            const syncData = data.syncData || {};
            const statusData = data.statusData || {};
            const groups = data.groups || statusData.groups || [];
            const summary = buildGroupSyncSummary(syncData, { ...statusData, groups });
            const endedAt = new Date();
            const seconds = Math.max(1, Math.round((endedAt.getTime() - startedAt.getTime()) / 1000));

            setGroups(groups);
            setGroupSyncSummary(summary);
            pushLog(`全部执行完成，用时 ${seconds} 秒。`);
            pushLog(`汇总：当前 ${summary.totalGroups} 个群，启用 ${summary.enabledCount} 个，禁用 ${summary.disabledTotalCount} 个，本次失效 ${summary.invalidCount} 个。`);
            setToastText(`🎉 同步成功！新增 ${syncData.added_count || 0} 个群组，已更新 ${statusData.updated_count || 0} 个群组状态。`);
            setTimeout(() => setToastText(''), 4000);
            source.close();
            resolve();
          } catch (err: any) {
            source.close();
            reject(err);
          }
        });

        source.addEventListener('sync_error', (event: MessageEvent) => {
          let message = "同步流连接失败";
          try {
            const data = JSON.parse(event.data);
            message = data?.message || message;
          } catch {
            if (event.data) message = event.data;
          }
          pushLog(`同步失败：${message}`);
          setToastText(`❌ 同步失败: ${message}`);
          setTimeout(() => setToastText(''), 4000);
          source.close();
          reject(new Error(message));
        });

        source.onerror = () => {
          pushLog("同步流连接中断。");
          setToastText("❌ 同步流连接中断");
          setTimeout(() => setToastText(''), 4000);
          source.close();
          reject(new Error("同步流连接中断"));
        };
      });
    } catch (err: any) {
      if (err?.message) {
        console.error("Group sync stream failed:", err);
      }
    } finally {
      sourceRef.current?.close();
      setGroupSyncRunning(false);
    }
  };

  const handleAddGroupCategory = async () => {
    const name = newCategoryName.trim();
    if (!name) {
      alert("请输入群组类型名称");
      return;
    }
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/group-categories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        alert(`添加类型失败：${data.detail || '未知原因'}`);
        return;
      }
      setNewCategoryName('');
      await fetchGroupCategories();
      setToastText(`已添加群组类型：${name}`);
      setTimeout(() => setToastText(''), 2000);
    } catch (err: any) {
      alert(`添加类型失败：${err.message}`);
    }
  };

  const handleRenameGroupCategory = async (oldName: string) => {
    const newName = prompt(`将类型「${oldName}」重命名为：`, oldName)?.trim();
    if (!newName || newName === oldName) return;
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/group-categories/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_name: oldName, new_name: newName }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        alert(`重命名失败：${data.detail || '未知原因'}`);
        return;
      }
      await Promise.all([fetchGroupCategories(), fetchGroups()]);
      setToastText(`已重命名为：${newName}`);
      setTimeout(() => setToastText(''), 2000);
    } catch (err: any) {
      alert(`重命名失败：${err.message}`);
    }
  };

  const handleDeleteGroupCategory = async (name: string) => {
    if (!confirm(`确定删除群组类型「${name}」吗？如果已有群组使用该类型，系统会拒绝删除。`)) return;
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/group-categories/${encodeURIComponent(name)}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        alert(`删除类型失败：${data.detail || '未知原因'}`);
        return;
      }
      await fetchGroupCategories();
      setToastText(`已删除群组类型：${name}`);
      setTimeout(() => setToastText(''), 2000);
    } catch (err: any) {
      alert(`删除类型失败：${err.message}`);
    }
  };

  const ignoreSingleScraped = async (id: string) => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/scraped-groups/batch-action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ids: [id],
          action: 'ignore'
        })
      });
      if (res.ok) {
        setToastText("已忽略该群组");
        setTimeout(() => setToastText(''), 2000);
        fetchScrapedGroups();
      }
    } catch (err: any) {
      console.error("Failed to ignore single group:", err);
    }
  };

  const activateSingleScraped = async (id: string) => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/scraped-groups/batch-action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ids: [id],
          action: 'unignore'
        })
      });
      if (res.ok) {
        setToastText("已重新激活该群组");
        setTimeout(() => setToastText(''), 2000);
        fetchScrapedGroups();
      }
    } catch (err: any) {
      console.error("Failed to activate single group:", err);
    }
  };



  const handleResolveGroup = async () => {

    const links = newGroupLinks.split('\n').map(l => l.trim()).filter(Boolean);

    if (links.length === 0) {

      setToastText("⚠️ 请输入至少一个群组链接或ID");

      setTimeout(() => setToastText(''), 2500);

      return;

    }

    setResolvingGroup(true);

    const backendUrl = BASE_URL;

    let successCount = 0;

    let failedList: string[] = [];

    let errorDetails: string[] = [];



    for (let i = 0; i < links.length; i++) {

      const link = links[i];

      setToastText(`正在校验第 ${i + 1}/${links.length} 个链接: ${link}...`);

      

      const controller = new AbortController();

      const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 seconds timeout



      try {

        const res = await fetch(`${backendUrl}/api/groups/resolve`, {

          method: 'POST',

          headers: {

            'Content-Type': 'application/json',

          },

          body: JSON.stringify({ link, category: newGroupCategory }),

          signal: controller.signal

        });

        

        clearTimeout(timeoutId);



        if (res.ok) {

          successCount++;

        } else {

          // If the endpoint is not found (404) or server has crashed (500+), treat as network/service outage

          if (res.status === 404 || res.status >= 500) {

            failedList.push(link);

            errorDetails.push(`${link}: 后端服务响应异常 (${res.status})，已自动停止后续执行。`);

            setToastText(`⚠️ 后端服务返回错误码 ${res.status}，已停止执行后续导入。`);

            setTimeout(() => setToastText(''), 3500);

            break; // Stop execution

          } else {

            // Standard validation error (e.g. 400 Bad Request, invite expired, user limit reached)

            const data = await res.json();

            const detail = data.detail || '';

            if (detail.includes('已在列表中') || detail.includes('无需重复添加')) {

              console.log(`群组已在列表中，已自动排重跳过: ${link}`);

            } else {

              failedList.push(link);

              errorDetails.push(`${link}: 校验失败 - ${detail || '原因未知'}`);

            }

            // Continue execution to next group

          }

        }

      } catch (err: any) {

        clearTimeout(timeoutId);

        

        if (err.name === 'AbortError') {

          // Single group got stuck / timed out

          failedList.push(link);

          errorDetails.push(`${link}: 校验超时 (15s) - 目标链接在电报端响应卡死，已记录并跳过。`);

          // Continue execution to next group

        } else {

          // Connection refused or failed to fetch (network disconnect with backend)

          failedList.push(link);

          errorDetails.push(`${link}: 连接后端失败 (${err.message})，已停止后续执行。`);

          setToastText(`⚠️ 无法连接到后端接口，已停止执行后续导入。`);

          setTimeout(() => setToastText(''), 3500);

          break; // Stop execution

        }

      }

    }



    setToastText('');

    setResolvingGroup(false);



    if (failedList.length === 0) {

      setToastText(`🎉 成功导入全部 ${successCount} 个群组！`);

      setTimeout(() => setToastText(''), 3000);

      setShowAddGroupModal(false);

      setNewGroupLinks('');

      setNewGroupCategory('中文广告');

      fetchGroups();

    } else {

      setBatchResult({

        successCount,

        failedCount: failedList.length,

        errorDetails

      });

      setShowBatchResultModal(true);

      setNewGroupLinks(failedList.join('\n'));

      fetchGroups();

    }

  };



  const handleToggleSelectGroup = (groupId: string) => {

    setSelectedGroupIds(prev => 

      prev.includes(groupId) ? prev.filter(id => id !== groupId) : [...prev, groupId]

    );

  };



  const handleToggleSelectAllGroups = () => {

    if (selectedGroupIds.length === groups.length) {

      setSelectedGroupIds([]);

    } else {

      setSelectedGroupIds(groups.map(g => g.id));

    }

  };



  const handleBatchDeleteGroups = async () => {

    if (selectedGroupIds.length === 0) return;

    if (!confirm(`确定要批量删除已选中的 ${selectedGroupIds.length} 个群组吗？`)) {

      return;

    }

    const backendUrl = BASE_URL;

    try {

      const idsToDelete = [...selectedGroupIds];

      setGroups(prev => prev.filter(g => !idsToDelete.includes(g.id)));

      setSelectedGroupIds([]);

      setIsBatchManaging(false);



      const res = await fetch(`${backendUrl}/api/groups/batch-delete`, {

        method: 'POST',

        headers: {

          'Content-Type': 'application/json',

        },

        body: JSON.stringify({ ids: idsToDelete }),

      });

      if (res.ok) {

        setToastText('批量删除群组成功');

        setTimeout(() => setToastText(''), 2000);

      }

      fetchGroups();

    } catch (err) {

      console.error("Failed to batch delete groups:", err);

      fetchGroups();

    }

  };



  const handleBatchUpdateCategory = async (category: '中文广告' | '英文广告') => {

    if (selectedGroupIds.length === 0) return;

    const backendUrl = BASE_URL;

    try {

      const idsToUpdate = [...selectedGroupIds];

      setGroups(prev => prev.map(g => idsToUpdate.includes(g.id) ? { ...g, category } : g));

      setSelectedGroupIds([]);

      setIsBatchManaging(false);



      const res = await fetch(`${backendUrl}/api/groups/batch-update-category`, {

        method: 'POST',

        headers: {

          'Content-Type': 'application/json',

        },

        body: JSON.stringify({ ids: idsToUpdate, category }),

      });

      if (res.ok) {

        setToastText(`已成功将 ${idsToUpdate.length} 个群组设为${category}`);

        setTimeout(() => setToastText(''), 2500);

      }

      fetchGroups();

    } catch (err) {

      console.error("Failed to batch update category:", err);

      fetchGroups();

    }

  };

  const handleUpdateGroupCategory = async (groupId: string, newCategory: string) => {
    const backendUrl = BASE_URL;
    try {
      setGroups(prev => prev.map(g => g.id === groupId ? { ...g, category: newCategory } : g));

      const res = await fetch(`${backendUrl}/api/groups/update-category`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: groupId, category: newCategory }),
      });

      if (res.ok) {
        setToastText('已成功修改群组类型');
        setTimeout(() => setToastText(''), 2000);
      } else {
        const data = await res.json();
        alert(`修改群组类型失败：${data.detail || '未知错误'}`);
        fetchGroups();
      }
    } catch (err: any) {
      alert(`修改群组类型失败: ${err.message}`);
      fetchGroups();
    }
  };



  if (false) {

    console.log(handleCreateChatFolder);

  }



  // Smart Finder / Scraper & AI states
  const [hasGeminiKey, setHasGeminiKey] = useState<boolean>(false);
  const [geminiKeyPreview, setGeminiKeyPreview] = useState<string>('');
  const [newGeminiKey, setNewGeminiKey] = useState<string>('');
  const [showGeminiConfigModal, setShowGeminiConfigModal] = useState<boolean>(false);
  const [savingGeminiKey, setSavingGeminiKey] = useState<boolean>(false);

  const [hasDeepSeekKey, setHasDeepSeekKey] = useState<boolean>(false);
  const [deepSeekKeyPreview, setDeepSeekKeyPreview] = useState<string>('');
  const [newDeepSeekKey, setNewDeepSeekKey] = useState<string>('');
  const [showDeepSeekConfigModal, setShowDeepSeekConfigModal] = useState<boolean>(false);
  const [savingDeepSeekKey, setSavingDeepSeekKey] = useState<boolean>(false);

  const [scrapedKeywords, setScrapedKeywords] = useState<string>(() => {
    return localStorage.getItem('rosepay_scraped_keywords') || '';
  });

  useEffect(() => {
    localStorage.setItem('rosepay_scraped_keywords', scrapedKeywords);
  }, [scrapedKeywords]);
  const [scrapedMinMembers, setScrapedMinMembers] = useState<number>(1000);
  const [scrapedMaxPages, setScrapedMaxPages] = useState<number>(5);
  const [scrapedContinuous, setScrapedContinuous] = useState<boolean>(false);
  const [scrapedIntervalMinutes, setScrapedIntervalMinutes] = useState<number>(30);
  
  const [scrapedAutoJoin, setScrapedAutoJoin] = useState<boolean>(() => {
    return localStorage.getItem('rosepay_scraped_auto_join') === 'true';
  });
  const [scrapedAutoJoinMinScore, setScrapedAutoJoinMinScore] = useState<number>(() => {
    const saved = localStorage.getItem('rosepay_scraped_auto_join_min_score');
    return saved ? parseInt(saved) : 70;
  });
  const [scrapedMaxRounds, setScrapedMaxRounds] = useState<number | ''>(() => {
    const saved = localStorage.getItem('rosepay_scraped_max_rounds');
    return saved ? parseInt(saved) : '';
  });
  const [scrapedGroupsPerRound, setScrapedGroupsPerRound] = useState<number>(() => {
    const saved = localStorage.getItem('rosepay_scraped_groups_per_round');
    return saved ? parseInt(saved) : 10;
  });
  const [scrapedRoundInterval, setScrapedRoundInterval] = useState<number>(() => {
    const saved = localStorage.getItem('rosepay_scraped_round_interval');
    return saved ? parseInt(saved) : 5;
  });

  useEffect(() => {
    localStorage.setItem('rosepay_scraped_auto_join', scrapedAutoJoin.toString());
  }, [scrapedAutoJoin]);
  useEffect(() => {
    localStorage.setItem('rosepay_scraped_auto_join_min_score', scrapedAutoJoinMinScore.toString());
  }, [scrapedAutoJoinMinScore]);
  useEffect(() => {
    localStorage.setItem('rosepay_scraped_max_rounds', scrapedMaxRounds === '' ? '' : scrapedMaxRounds.toString());
  }, [scrapedMaxRounds]);
  useEffect(() => {
    localStorage.setItem('rosepay_scraped_groups_per_round', scrapedGroupsPerRound.toString());
  }, [scrapedGroupsPerRound]);
  useEffect(() => {
    localStorage.setItem('rosepay_scraped_round_interval', scrapedRoundInterval.toString());
  }, [scrapedRoundInterval]);

  const [scrapedSortBy, setScrapedSortBy] = useState<string>('default');
  const [scrapedGroups, setScrapedGroups] = useState<any[]>([]);
  const [selectedScrapedGroupIds, setSelectedScrapedGroupIds] = useState<string[]>([]);
  const [categoryToAssignScraped, setCategoryToAssignScraped] = useState<string>('中文广告');
  const [scrapedFilterCategory, setScrapedFilterCategory] = useState<string>('all');
  const [scrapedMinScoreFilter, setScrapedMinScoreFilter] = useState<number>(0);
  
  const [scrapedTaskStatus, setScrapedTaskStatus] = useState<string>('idle');
  const [scrapedTaskProgress, setScrapedTaskProgress] = useState<{current: number, total: number}>({current: 0, total: 0});
  const [scrapedTaskLogs, setScrapedTaskLogs] = useState<string[]>([]);
  const [scrapedTaskError, setScrapedTaskError] = useState<string | null>(null);
  const [isSearchingScraped, setIsSearchingScraped] = useState<boolean>(false);

  // --- BUSINESS EXPANSION AGENT STATE ---
  const [expansionTarget, setExpansionTarget] = useState<string>(() => {
    return localStorage.getItem('rosepay_expansion_target') || '在印度当地的生活聊天群（交友、生活交流）以及 OTC/USDT/支付相关的专业群中拓展业务';
  });

  useEffect(() => {
    localStorage.setItem('rosepay_expansion_target', expansionTarget);
  }, [expansionTarget]);
  const [expansionStatus, setExpansionStatus] = useState<string>('idle');
  const [expansionKeyword, setExpansionKeyword] = useState<string>('');
  const [expansionLogs, setExpansionLogs] = useState<string[]>([]);
  const [expansionGroups, setExpansionGroups] = useState<any[]>([]);
  const [expansionInterval, setExpansionInterval] = useState<number>(15);

  const [expansionAutoJoin, setExpansionAutoJoin] = useState<boolean>(() => {
    return localStorage.getItem('rosepay_expansion_auto_join') === 'true';
  });
  const [expansionAutoJoinMinScore, setExpansionAutoJoinMinScore] = useState<number>(() => {
    const saved = localStorage.getItem('rosepay_expansion_auto_join_min_score');
    return saved ? parseInt(saved) : 70;
  });
  const [expansionMaxRounds, setExpansionMaxRounds] = useState<number | ''>(() => {
    const saved = localStorage.getItem('rosepay_expansion_max_rounds');
    return saved ? parseInt(saved) : '';
  });
  const [expansionGroupsPerRound, setExpansionGroupsPerRound] = useState<number>(() => {
    const saved = localStorage.getItem('rosepay_expansion_groups_per_round');
    return saved ? parseInt(saved) : 10;
  });
  const [expansionRoundInterval, setExpansionRoundInterval] = useState<number>(() => {
    const saved = localStorage.getItem('rosepay_expansion_round_interval');
    return saved ? parseInt(saved) : 5;
  });

  useEffect(() => {
    localStorage.setItem('rosepay_expansion_auto_join', expansionAutoJoin.toString());
  }, [expansionAutoJoin]);
  useEffect(() => {
    localStorage.setItem('rosepay_expansion_auto_join_min_score', expansionAutoJoinMinScore.toString());
  }, [expansionAutoJoinMinScore]);
  useEffect(() => {
    localStorage.setItem('rosepay_expansion_max_rounds', expansionMaxRounds === '' ? '' : expansionMaxRounds.toString());
  }, [expansionMaxRounds]);
  useEffect(() => {
    localStorage.setItem('rosepay_expansion_groups_per_round', expansionGroupsPerRound.toString());
  }, [expansionGroupsPerRound]);
  useEffect(() => {
    localStorage.setItem('rosepay_expansion_round_interval', expansionRoundInterval.toString());
  }, [expansionRoundInterval]);
  const [selectedExpansionGroupIds, setSelectedExpansionGroupIds] = useState<string[]>([]);


  const fetchGeminiConfig = async () => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/config/gemini`);
      if (res.ok) {
        const data = await res.json();
        setHasGeminiKey(data.has_key);
        setGeminiKeyPreview(data.key_preview || '');
      }
    } catch (err) {
      console.error("Failed to fetch Gemini config:", err);
    }
  };

  const saveGeminiKey = async () => {
    if (!newGeminiKey.trim()) return;
    setSavingGeminiKey(true);
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/config/gemini`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: newGeminiKey.trim() })
      });
      if (res.ok) {
        setToastText("Gemini API Key 保存成功");
        setTimeout(() => setToastText(''), 2000);
        setNewGeminiKey('');
        setShowGeminiConfigModal(false);
        fetchGeminiConfig();
      } else {
        const data = await res.json();
        alert(`保存失败: ${data.detail || '未知错误'}`);
      }
    } catch (err: any) {
      alert(`保存失败: ${err.message}`);
    } finally {
      setSavingGeminiKey(false);
    }
  };

  const fetchDeepSeekConfig = async () => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/config/deepseek`);
      if (res.ok) {
        const data = await res.json();
        setHasDeepSeekKey(data.has_key);
        setDeepSeekKeyPreview(data.key_preview || '');
      }
    } catch (err) {
      console.error("Failed to fetch DeepSeek config:", err);
    }
  };

  const saveDeepSeekKey = async () => {
    if (!newDeepSeekKey.trim()) return;
    setSavingDeepSeekKey(true);
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/config/deepseek`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: newDeepSeekKey.trim() })
      });
      if (res.ok) {
        setToastText("DeepSeek API Key 保存成功");
        setTimeout(() => setToastText(''), 2000);
        setNewDeepSeekKey('');
        setShowDeepSeekConfigModal(false);
        fetchDeepSeekConfig();
      } else {
        const data = await res.json();
        alert(`保存失败: ${data.detail || '未知错误'}`);
      }
    } catch (err: any) {
      alert(`保存失败: ${err.message}`);
    } finally {
      setSavingDeepSeekKey(false);
    }
  };

  const fetchScrapedGroups = async () => {
    const backendUrl = BASE_URL;
    try {
      let url = `${backendUrl}/api/scraped-groups`;
      const params: string[] = [];
      if (scrapedFilterCategory !== 'all') {
        params.push(`category=${scrapedFilterCategory}`);
      }
      if (scrapedMinScoreFilter > 0) {
        params.push(`min_score=${scrapedMinScoreFilter}`);
      }
      if (scrapedSortBy) {
        params.push(`sort_by=${scrapedSortBy}`);
      }
      if (params.length > 0) {
        url += `?${params.join('&')}`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setScrapedGroups(data);
      }
    } catch (err) {
      console.error("Failed to fetch scraped groups:", err);
    }
  };

  const toggleScrapedGroupImportance = async (groupId: string, currentIsImportant: boolean) => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/scraped-groups/${groupId}/toggle-important`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_important: !currentIsImportant })
      });
      if (res.ok) {
        fetchScrapedGroups();
        fetchExpansionGroups();
      } else {
        const data = await res.json();
        alert(`切换重点标记失败: ${data.detail || '未知错误'}`);
      }
    } catch (err: any) {
      alert(`切换重点标记失败: ${err.message}`);
    }
  };

  const fetchExpansionGroups = async () => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/expansion/groups`);
      if (res.ok) {
        const data = await res.json();
        setExpansionGroups(data);
      }
    } catch (err) {
      console.error("Failed to fetch expansion groups:", err);
    }
  };

  const fetchExpansionStatus = async () => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/expansion/status`);
      if (res.ok) {
        const data = await res.json();
        setExpansionStatus(data.status);
        if (data.target_desc) {
          setExpansionTarget(data.target_desc);
        }
        setExpansionKeyword(data.current_keyword || '');
        setExpansionLogs(data.logs || []);
      }
    } catch (err) {
      console.error("Failed to fetch expansion status:", err);
    }
  };

  const startExpansion = async () => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/expansion/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_desc: expansionTarget,
          loop_interval_minutes: expansionInterval,
          auto_join: expansionAutoJoin,
          auto_join_min_score: expansionAutoJoinMinScore,
          max_rounds: expansionMaxRounds === '' ? null : expansionMaxRounds,
          groups_per_round: expansionGroupsPerRound,
          round_interval_minutes: expansionRoundInterval
        })
      });
      if (res.ok) {
        setToastText("自主业务拓展任务已启动");
        setTimeout(() => setToastText(''), 2000);
        fetchExpansionStatus();
        fetchExpansionGroups();
      } else {
        const data = await res.json();
        alert(`启动失败: ${data.detail || '未知错误'}`);
      }
    } catch (err: any) {
      alert(`启动异常: ${err.message}`);
    }
  };

  const pauseExpansion = async () => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/expansion/pause`, {
        method: 'POST'
      });
      if (res.ok) {
        setToastText("自主业务拓展任务已暂停");
        setTimeout(() => setToastText(''), 2000);
        fetchExpansionStatus();
      }
    } catch (err: any) {
      alert(`暂停异常: ${err.message}`);
    }
  };

  const batchActionExpansionGroups = async (action: 'join' | 'ignore' | 'delete' | 'unignore', ids: string[]) => {
    if (ids.length === 0) return;
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/scraped-groups/batch-action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ids,
          action,
          category_to_assign: categoryToAssignScraped
        })
      });
      if (res.ok) {
        setToastText(`已成功对 ${ids.length} 个群组执行 ${action === 'join' ? '导入加群' : action === 'ignore' ? '忽略' : action === 'unignore' ? '激活' : '删除'}`);
        setTimeout(() => setToastText(''), 2000);
        setSelectedExpansionGroupIds([]);
        fetchExpansionGroups();
        fetchGroups(); // Refresh main group list too
      } else {
        const data = await res.json();
        alert(`操作失败: ${data.detail}`);
      }
    } catch (err: any) {
      alert(`操作异常: ${err.message}`);
    }
  };

  const fetchScrapedTaskStatus = async () => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/scraped-groups/task-status`);
      if (res.ok) {
        const data = await res.json();
        setScrapedTaskStatus(data.status);
        setScrapedTaskProgress(data.progress || {current: 0, total: 0});
        setScrapedTaskLogs(data.logs || []);
        setScrapedTaskError(data.error);
        if (data.status === 'running') {
          setIsSearchingScraped(true);
        }
      }
    } catch (err) {
      console.error("Failed to fetch scraper task status:", err);
    }
  };

  const startScrapedSearchTask = async () => {
    if (!scrapedKeywords.trim()) {
      alert("请输入搜群关键词！");
      return;
    }
    const keywordsList = scrapedKeywords.split(/[\n,，]+/).map(k => k.trim()).filter(Boolean);
    if (keywordsList.length === 0) {
      alert("请输入有效的关键词！");
      return;
    }
    setIsSearchingScraped(true);
    setScrapedTaskStatus('running');
    setScrapedTaskLogs([]);
    setScrapedTaskProgress({current: 0, total: 0});
    setScrapedTaskError(null);
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/scraped-groups/search-task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keywords: keywordsList,
          min_members: scrapedMinMembers,
          max_pages: scrapedMaxPages,
          continuous: scrapedContinuous,
          interval_minutes: scrapedIntervalMinutes,
          auto_join: scrapedAutoJoin,
          auto_join_min_score: scrapedAutoJoinMinScore,
          max_rounds: scrapedMaxRounds === '' ? null : scrapedMaxRounds,
          groups_per_round: scrapedGroupsPerRound,
          round_interval_minutes: scrapedRoundInterval
        })
      });
      if (!res.ok) {
        const data = await res.json();
        alert(`启动失败: ${data.detail || '未知错误'}`);
        setIsSearchingScraped(false);
        setScrapedTaskStatus('idle');
      } else {
        setToastText("搜群与AI分析任务已在后台启动！");
        setTimeout(() => setToastText(''), 2500);
      }
    } catch (err: any) {
      alert(`启动失败: ${err.message}`);
      setIsSearchingScraped(false);
      setScrapedTaskStatus('idle');
    }
  };

  const stopScrapedSearchTask = async () => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/scraped-groups/search-task/stop`, {
        method: 'POST'
      });
      if (res.ok) {
        setToastText("正在停止搜群任务...");
        setTimeout(() => setToastText(''), 2000);
      }
    } catch (err) {
      console.error("Failed to stop scraper task:", err);
    }
  };

  const singleJoinScraped = async (id: string, category: string) => {
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/scraped-groups/batch-action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ids: [id],
          action: 'join',
          category_to_assign: category
        })
      });
      if (res.ok) {
        setToastText("已加入群组库");
        setTimeout(() => setToastText(''), 2000);
        fetchScrapedGroups();
        fetchExpansionGroups();
        fetchGroups();
      } else {
        const data = await res.json();
        alert(`加入失败: ${data.detail || '未知原因'}`);
      }
    } catch (err: any) {
      console.error("Failed to join single scraped group:", err);
    }
  };

  const handleBatchActionScraped = async (action: 'join' | 'ignore' | 'delete') => {
    if (selectedScrapedGroupIds.length === 0) {
      alert("请至少勾选一个群组！");
      return;
    }
    const actionCN = action === 'join' ? '导入加群任务' : action === 'ignore' ? '忽略' : '删除记录';
    if (!confirm(`确认要对选中的 ${selectedScrapedGroupIds.length} 个群组执行【${actionCN}】操作吗？`)) {
      return;
    }
    const backendUrl = BASE_URL;
    try {
      const res = await fetch(`${backendUrl}/api/scraped-groups/batch-action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ids: selectedScrapedGroupIds,
          action,
          category_to_assign: categoryToAssignScraped
        })
      });
      if (res.ok) {
        const data = await res.json();
        setToastText(`成功对 ${data.count} 个群组执行【${actionCN}】！`);
        setTimeout(() => setToastText(''), 3000);
        setSelectedScrapedGroupIds([]);
        fetchScrapedGroups();
        if (action === 'join') {
          fetchGroups(); // Refresh main groups library
        }
      } else {
        const data = await res.json();
        alert(`操作失败: ${data.detail || '未知错误'}`);
      }
    } catch (err: any) {
      alert(`操作异常: ${err.message}`);
    }
  };

  // Fetch Gemini & DeepSeek config on mount
  useEffect(() => {
    if (isLoggedIn) {
      fetchGeminiConfig();
      fetchDeepSeekConfig();
      fetchScrapedGroups();
      fetchScrapedTaskStatus();
    }
  }, [isLoggedIn]);

  // Poll search task status when running
  useEffect(() => {
    if (!isLoggedIn) return;
    let timer: any = null;
    
    const checkStatus = async () => {
      const backendUrl = BASE_URL;
      try {
        const res = await fetch(`${backendUrl}/api/scraped-groups/task-status`);
        if (res.ok) {
          const data = await res.json();
          setScrapedTaskStatus(data.status);
          setScrapedTaskProgress(data.progress || {current: 0, total: 0});
          setScrapedTaskLogs(data.logs || []);
          setScrapedTaskError(data.error);
          
          if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped') {
            setIsSearchingScraped(false);
            fetchScrapedGroups(); // Refresh list on complete
          } else if (data.status === 'running') {
            setIsSearchingScraped(true);
          }
        }
      } catch (err) {
        console.error("Failed to poll scraper task status:", err);
      }
    };

    if (scrapedTaskStatus === 'running' || isSearchingScraped || activeTab === 'finder') {
      checkStatus();
      timer = setInterval(checkStatus, 3000);
    }
    
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [scrapedTaskStatus, isSearchingScraped, isLoggedIn]);

  useEffect(() => {
    if (isLoggedIn) {
      fetchScrapedGroups();
    }
  }, [scrapedFilterCategory, scrapedMinScoreFilter, scrapedSortBy, isLoggedIn]);

  // Fetch Business Expansion on mount/tab change
  useEffect(() => {
    if (isLoggedIn) {
      fetchExpansionStatus();
      fetchExpansionGroups();
    }
  }, [isLoggedIn, activeTab, accountViewScope]);

  // Poll Business Expansion status when running or if tab is open
  useEffect(() => {
    if (!isLoggedIn) return;
    let timer: any = null;
    
    const checkStatus = async () => {
      await fetchExpansionStatus();
      if (activeTab === 'expansion') {
        await fetchExpansionGroups();
      }
    };

    if (expansionStatus === 'running' || activeTab === 'expansion') {
      checkStatus();
      timer = setInterval(checkStatus, 3000);
    }
    
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [expansionStatus, activeTab, isLoggedIn]);

  // Fetch Business Expansion on mount/tab change
  useEffect(() => {
    if (isLoggedIn) {
      fetchExpansionStatus();
      fetchExpansionGroups();
    }
  }, [isLoggedIn, activeTab]);

  // Poll Business Expansion status when running or if tab is open
  useEffect(() => {
    if (!isLoggedIn) return;
    let timer: any = null;
    
    const checkStatus = async () => {
      await fetchExpansionStatus();
      if (activeTab === 'expansion') {
        await fetchExpansionGroups();
      }
    };

    if (expansionStatus === 'running' || activeTab === 'expansion') {
      checkStatus();
      timer = setInterval(checkStatus, 3000);
    }
    
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [expansionStatus, activeTab, isLoggedIn]);

  useEffect(() => {
    checkAuthStatus();
    checkCurrentUser();



    // Fetch environment-specific proxy defaults

    const fetchDefaultProxy = async () => {
      const backendUrl = BASE_URL;

      try {

        const res = await fetch(`${backendUrl}/api/config/default-proxy`);

        if (res.ok) {

          const data = await res.json();

          setProxyEnabled(data.enabled);

          setProxyHost(data.host || '127.0.0.1');

          setProxyPort(data.port || 8800);

          setProxyUser(data.username || '');

          setProxyPass(data.password || '');

        }

      } catch (err) {

        console.error("Failed to fetch default proxy config:", err);

      }

    };

    fetchDefaultProxy();

  }, []);



  useEffect(() => {

    if (!isLoggedIn) return;

    if (activeTab === 'accounts' || activeTab === 'campaign' || activeTab === 'join') {

      fetchBackendAccounts();

    }

    if (activeTab === 'accounts') {

      fetchUsersList();

    }

    if (activeTab === 'groups' || activeTab === 'join' || activeTab === 'finder' || activeTab === 'expansion') {

      fetchGroups();
      fetchGroupCategories();

    }

    if (activeTab === 'finder') {
      setScrapedSortField('time');
      setScrapedSortOrder('desc');
    } else if (activeTab === 'expansion') {
      setExpansionSortField('time');
      setExpansionSortOrder('desc');
    }

    if (activeTab === 'users') {

      fetchUsersList();

      fetchCompaniesList();

    } else if (activeTab === 'permissions') {

      fetchRolePermissions();

    } else if (activeTab === 'bot_auth') {

      refreshBotPermissionPage();
      fetchUsersList();

    } else if (activeTab === 'join') {

      fetchLastJoinTask();

    }

  }, [activeTab, isLoggedIn]);



  useEffect(() => {

    if (!isLoggedIn) return;

    if (activeTab === 'campaign') {

      fetchCampaignTasks();

      fetchPredefinedAds();

      const interval = setInterval(() => {

        fetchCampaignTasks();

      }, 4000);

      return () => clearInterval(interval);

    }

    if (activeTab === 'logs') {
      fetchCampaignTasks();
      if (selectedLogTaskId) {
        fetchSelectedTaskLogs(selectedLogTaskId);
      }
      const interval = setInterval(() => {
        fetchCampaignTasks();
        if (selectedLogTaskId) {
          fetchSelectedTaskLogs(selectedLogTaskId);
        }
      }, 5000);
      return () => clearInterval(interval);
    }

  }, [activeTab, isLoggedIn]);
  useEffect(() => {
    if (activeTab === 'logs' && campaignTasks.length > 0 && !selectedLogTaskId) {
      const grouped = groupCampaignTasks(campaignTasks);
      if (grouped.length > 0) {
        setSelectedLogTaskId(grouped[0].id);
      }
    }
  }, [campaignTasks, activeTab, selectedLogTaskId]);




  // Poll logs for the active campaign task when details modal is open

  useEffect(() => {

    if (!isLoggedIn || !showCampaignLogsModal || !activeCampaignTaskId) return;

    const grouped = groupCampaignTasks(campaignTasks);
    const group = grouped.find(g => g.task_ids.includes(activeCampaignTaskId));
    const idsToFetch = group ? group.task_ids : [activeCampaignTaskId];

    fetchCampaignTaskLogs(idsToFetch);

    const interval = setInterval(() => {

      fetchCampaignTaskLogs(idsToFetch);

    }, 3000);



    return () => clearInterval(interval);

  }, [showCampaignLogsModal, activeCampaignTaskId, isLoggedIn, campaignTasks]);



  useEffect(() => {

    if (isLoggedIn && allowedTabs.length > 0) {

      if (!allowedTabs.includes(activeTab)) {

        setActiveTab(allowedTabs[0] as any);

      }

    }

  }, [allowedTabs, activeTab, isLoggedIn]);





  useEffect(() => {

    if (!joinTaskId || !joinRunning) return;



    let timer: any = null;

    const pollStatus = async () => {

      const backendUrl = BASE_URL;

      try {

        const res = await fetch(`${backendUrl}/api/groups/join-task/status/${joinTaskId}`);

        if (res.ok) {

          const data = await res.json();

          setJoinProgress(data.progress || { current: 0, total: 0 });

          setJoinResults(data.results || []);

          setJoinLogs(data.logs || []);

          

          if (data.status === 'completed' || data.status === 'stopped') {

            setJoinRunning(false);

            fetchTaskHistory();

            setToastText(data.status === 'completed' ? "入群任务已圆满完成！" : "入群任务已停止。");

            setTimeout(() => setToastText(''), 3000);

            

            // Check for invalid groups to prompt deletion

            const invalidResults = (data.results || []).filter((r: any) => r.status === 'invalid');

            const uniqueInvalidGroups: { id: string; title: string; link: string }[] = [];

            const seenIds = new Set<string>();

            for (const r of invalidResults) {

              if (r.group_id && !seenIds.has(r.group_id)) {

                seenIds.add(r.group_id);

                uniqueInvalidGroups.push({

                  id: r.group_id,

                  title: r.title || '',

                  link: r.link

                });

              }

            }

            if (uniqueInvalidGroups.length > 0) {

              setInvalidGroupsToDelete(uniqueInvalidGroups);

              setShowInvalidGroupsModal(true);

            }

          }

        }

      } catch (err) {

        console.error("Error polling join task:", err);

      }

    };



    pollStatus();

    timer = setInterval(pollStatus, 2000);



    return () => {

      if (timer) clearInterval(timer);

    };

  }, [joinTaskId, joinRunning, isLoggedIn]);



  useEffect(() => {

    if (activeTab === 'join' && !joinRunning && isLoggedIn) {

      fetchTaskHistory();

    }

  }, [activeTab, joinRunning, isLoggedIn]);







  const handleBatchLoginAll = async () => {

    const accountsToLogin = accountsPool

      .filter(acc => acc.status === 'idle' || acc.status === 'failed' || acc.status === 'waiting_code' || acc.status === '2fa_required');

      

    if (accountsToLogin.length === 0) {

      alert("没有可以登录的账号 (需要是待登录、登录失败或等待输入状态)");

      return;

    }

    

    setToastText(`开始批量登录 ${accountsToLogin.length} 个账号...`);

    setTimeout(() => setToastText(''), 3000);

    

    for (const acc of accountsToLogin) {

      startLoginFlow(acc.accountId);

      await new Promise(resolve => setTimeout(resolve, 1500));

    }

  };



  // Interactive handler: Import Accounts

  const handleImportAccounts = () => {
    const lines = textareaValue.split('\n').map(line => line.trim()).filter(line => line.length > 0);
    if (lines.length === 0) {
      alert('请输入合法的手机号或组合串（每行一个）');
      return;
    }

    const newAccounts: Account[] = [];

    for (const line of lines) {
      let phone = '';
      let url = '';
      
      // 智能兼容切分：优先使用 ----，若无则支持空格、Tab、逗号等
      if (line.includes('----')) {
        const parts = line.split('----');
        phone = parts[0].trim();
        url = parts.length > 1 ? parts[1].trim() : '';
      } else {
        // 用正则剥离出第一串数字作为手机号，剥离出 http 开头的网址作为 URL
        const phoneMatch = line.match(/(\+?[0-9\s\-]{7,20})/);
        const urlMatch = line.match(/(https?:\/\/[^\s]+)/);
        if (phoneMatch) {
          phone = phoneMatch[1].replace(/[\s\-]/g, '');
        }
        if (urlMatch) {
          url = urlMatch[1].trim();
        }
      }
      
      let pageId = '';
      if (url) {
        // 兼容新旧平台的 token 提取
        const tokenMatch = url.match(/token=([a-zA-Z0-9\-]+)/) || url.match(/(?:https?:\/\/[^\/]+\/)?([a-zA-Z0-9\-]+)(?:\/GetHTML)?/);
        if (tokenMatch) {
          pageId = tokenMatch[1];
        }
      }

      const accountId = phone.replace(/[^a-zA-Z0-9]/g, '');
      if (!accountId) {
        alert(`无效的手机号码格式: "${phone}"`);
        return;
      }
      
      newAccounts.push({

        phone,

        scraperUrl: url,

        status: 'idle',

        code: '',

        pass2fa: '',

        defaultPass2fa: '',

        statusText: url ? '就绪，等待自动检测并登录' : '就绪，等待发送验证码',

        accountId,

        pageId,

        showManual2fa: false

      });

    }



    setAccountsPool(prev => [...prev, ...newAccounts]);

    setTextareaValue('');

    setToastText(`已导入 ${lines.length} 个账号，开始自动检测并登录...`);

    setTimeout(() => setToastText(''), 3000);



    // Auto-run checking and login sequential flow

    setTimeout(async () => {

      let successCount = 0;

      let failedCount = 0;

      const successIds: string[] = [];



      for (let i = 0; i < newAccounts.length; i++) {

        const acc = newAccounts[i];

        

        // Proactively check session first

        const backendUrl = BASE_URL;

        let isAuthorized = false;

        try {

          const res = await fetch(`${backendUrl}/api/login/status/${acc.accountId}`);

          if (res.ok) {

            const data = await res.json();

            if (data.is_authorized) {

              isAuthorized = true;

              setAccountsPool(prev => prev.map(a => a.accountId === acc.accountId ? {

                ...a,

                status: 'success',

                statusText: `已登录：${data.me || '在线'}`

              } : a));

              successCount++;

              successIds.push(acc.accountId);

            }

          }

        } catch (err) {

          console.error("Auto session check failed:", err);

        }

        

        // If not already logged in, start the login flow automatically

        if (!isAuthorized) {

          const result = await startLoginFlow(acc.accountId, acc);

          if (result === 'success') {

            successCount++;

            successIds.push(acc.accountId);

          } else {

            failedCount++;

          }

          // Wait 1.5 seconds between each starting process to avoid rate limiting

          await new Promise(resolve => setTimeout(resolve, 1500));

        }

      }



      // After all accounts in this batch are processed:

      setImportedBatchSuccessIds(successIds);

      setImportStats({

        total: newAccounts.length,

        success: successCount,

        failed: failedCount

      });

      if (successIds.length > 0) {
        setSelectedAccountIds(successIds);
        setShowBatchProfileModal(true);
      } else {
        setShowImportResultModal(true);
      }

    }, 100);

  };



  // Interactive handler: Delete Account

  const handleDeleteAccount = (accountId: string) => {

    setAccountsPool(prev => prev.filter(acc => acc.accountId !== accountId));

  };



  // Interactive handler: Update Account Code

  const handleUpdateCode = (accountId: string, code: string) => {

    setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? { ...acc, code } : acc));

  };



  // Interactive handler: Update Account 2FA Password

  const handleUpdatePass2fa = (accountId: string, pass2fa: string) => {

    setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? { ...acc, pass2fa } : acc));

  };



  // Automated Flow: Start Login Flow (Send phone -> Wait -> Scrape -> Submit Code with default 2fa)

  const startLoginFlow = async (accountId: string, accountOverride?: Account): Promise<'success' | 'failed' | '2fa_required'> => {

    const account = accountOverride || accountsPool.find(acc => acc.accountId === accountId);

    if (!account) return 'failed';

    

    setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

      ...acc,

      status: 'sending_code',

      code: '',

      pass2fa: '',

      defaultPass2fa: '',

      showManual2fa: false,

      statusText: '正在请求 Telegram 登录并发送手机号...'

    } : acc));



    const backendUrl = BASE_URL;



    try {

      const sendCodeRes = await fetch(`${backendUrl}/api/login/send-code`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({ account_id: account.accountId, phone: account.phone })

      });

      

      const sendCodeData = await sendCodeRes.json();

      if (!sendCodeRes.ok) {

        throw new Error(sendCodeData.detail || '发送验证码失败');

      }



      if (sendCodeData.status === 'authorized') {

        setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

          ...acc,

          status: 'success',

          statusText: '已登录（已授权）'

        } : acc));

        

        setLogs(prev => [{

          time: new Date().toLocaleTimeString(),

          folder: '系统',

          phone: account.phone,

          title: '已授权',

          action: '检测在线',

          status: 'success',

          detail: '客户端已经是授权登录状态，无需验证'

        }, ...prev]);

        return 'success';

      }



      setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

        ...acc,

        status: 'waiting_code',

        statusText: '验证码已请求，等待 4 秒以允许网页接收数据...'

      } : acc));



      await new Promise(resolve => setTimeout(resolve, 4000));



      if (!account.pageId) {

        setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

          ...acc,

          status: 'waiting_code',

          statusText: '未配置接码网页，请收到验证码后在下方手动输入'

        } : acc));

        return 'failed';

      }



      setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

        ...acc,

        status: 'fetching_code',

        statusText: '正在从网页接码平台自动提取验证码及2FA密码...'

      } : acc));



      const fetchRes = await fetch(`${backendUrl}/api/scraper/fetch?page_id=${account.pageId}`);

      if (!fetchRes.ok) {

        throw new Error('无法从网页拉取到验证码数据');

      }

      const fetchData = await fetchRes.json();

      const code = fetchData.code || '';

      const pass2fa = fetchData.pass2fa || '';



      if (!code) {

        setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

          ...acc,

          status: 'waiting_code',

          statusText: '网页尚未生成验证码，请稍后手动重试或手动输入'

        } : acc));

        return 'failed';

      }



      setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

        ...acc,

        status: 'submitting_code',

        code: code,

        pass2fa: pass2fa,

        defaultPass2fa: pass2fa,

        statusText: `已提取验证码: ${code} 与网页默认密码，正在验证登录...`

      } : acc));



      const submitRes = await fetch(`${backendUrl}/api/login/submit-code`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          account_id: account.accountId,

          code: code,

          pass2fa: pass2fa || null

        })

      });



      const submitData = await submitRes.json();

      if (!submitRes.ok) {

        throw new Error(submitData.detail || '提交登录验证失败');

      }



      if (submitData.status === '2fa_required') {

        setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

          ...acc,

          status: '2fa_required',

          showManual2fa: true,

          statusText: '网页默认密码错误或已失效。需手动输入 2FA 密码以进行登录。'

        } : acc));

        return '2fa_required';

      } else if (submitData.status === 'success') {

        setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

          ...acc,

          status: 'success',

          statusText: '登录成功'

        } : acc));

        

        setLogs(prev => [{

          time: new Date().toLocaleTimeString(),

          folder: '系统',

          phone: account.phone,

          title: '自动登录',

          action: '登录成功',

          status: 'success',

          detail: `使用验证码=${code} 与默认密码登录成功`

        }, ...prev]);

        return 'success';

      }

      return 'failed';



    } catch (err: any) {

      setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

        ...acc,

        status: 'failed',

        statusText: `登录失败: ${err.message}`

      } : acc));

      

      setLogs(prev => [{

        time: new Date().toLocaleTimeString(),

        folder: '系统',

        phone: account.phone,

        title: '登录异常',

        action: '登录失败',

        status: 'error',

        detail: err.message

      }, ...prev]);

      return 'failed';

    }

  };



  // Manual Flow: Submit manual verification code entered by user

  const submitManualCodeFlow = async (accountId: string) => {

    const account = accountsPool.find(acc => acc.accountId === accountId);

    if (!account) return;

    if (!account.code.trim()) {

      alert("请输入验证码");

      return;

    }

    

    setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

      ...acc,

      status: 'submitting_code',

      statusText: '正在提交您输入的验证码进行登录...'

    } : acc));



    const backendUrl = BASE_URL;



    try {

      const submitRes = await fetch(`${backendUrl}/api/login/submit-code`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          account_id: account.accountId,

          code: account.code.trim(),

          pass2fa: null

        })

      });



      const submitData = await submitRes.json();

      if (!submitRes.ok) {

        throw new Error(submitData.detail || '提交验证码失败');

      }



      if (submitData.status === '2fa_required') {

        setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

          ...acc,

          status: '2fa_required',

          showManual2fa: true,

          statusText: '验证码正确，需要输入二步验证密码以完成登录。'

        } : acc));

      } else if (submitData.status === 'success') {

        setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

          ...acc,

          status: 'success',

          statusText: '登录成功'

        } : acc));

        

        setLogs(prev => [{

          time: new Date().toLocaleTimeString(),

          folder: '系统',

          phone: account.phone,

          title: '手动验证码登录',

          action: '登录成功',

          status: 'success',

          detail: `手动输入验证码=${account.code}登录成功`

        }, ...prev]);

      }

    } catch (err: any) {

      setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

        ...acc,

        status: 'failed',

        statusText: `登录失败: ${err.message}`

      } : acc));

      

      setLogs(prev => [{

        time: new Date().toLocaleTimeString(),

        folder: '系统',

        phone: account.phone,

        title: '登录异常',

        action: '登录失败',

        status: 'error',

        detail: err.message

      }, ...prev]);

    }

  };



  // Manual Flow: Submit 2FA password entered manually by user

  const submit2FAFlow = async (accountId: string) => {

    const account = accountsPool.find(acc => acc.accountId === accountId);

    if (!account) return;

    

    setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

      ...acc,

      status: 'submitting_code',

      statusText: '正在提交您输入的 2FA 密码进行登录...'

    } : acc));



    const backendUrl = BASE_URL;



    try {

      const submitRes = await fetch(`${backendUrl}/api/login/submit-code`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          account_id: account.accountId,

          code: account.code,

          pass2fa: account.pass2fa || null

        })

      });



      const submitData = await submitRes.json();

      if (!submitRes.ok) {

        throw new Error(submitData.detail || '提交登录验证失败');

      }



      if (submitData.status === '2fa_required') {

        setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

          ...acc,

          status: '2fa_required',

          showManual2fa: true,

          statusText: '密码输入错误，请重新输入 2FA 密码后点击登录'

        } : acc));

      } else if (submitData.status === 'success') {

        setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

          ...acc,

          status: 'success',

          statusText: '登录成功'

        } : acc));

        

        setLogs(prev => [{

          time: new Date().toLocaleTimeString(),

          folder: '系统',

          phone: account.phone,

          title: '手动登录',

          action: '登录成功',

          status: 'success',

          detail: '手动输入 2FA 验证通过，登录成功'

        }, ...prev]);

      }

    } catch (err: any) {

      setAccountsPool(prev => prev.map(acc => acc.accountId === accountId ? {

        ...acc,

        status: 'failed',

        statusText: `登录失败: ${err.message}`

      } : acc));

    }

  };




  // Toggle dynamic metrics

  const renderCampaignLibraryPicker = () => {
    const selectableLibraryGroups = groups.filter(g => g.enabled);
    const allLibraryGroupIds = selectableLibraryGroups.map(g => g.id);
    const allSelected = allLibraryGroupIds.length > 0 && allLibraryGroupIds.every(id => selectedCampaignLibraryGroupIds.includes(id));

    return (
      <div className="flex flex-col gap-2 flex-grow min-h-[260px]">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold text-slate-600">从系统群组库选择目标群组</label>
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-slate-400">已选 {selectedCampaignLibraryGroupIds.length} 个</span>
            <button
              type="button"
              onClick={() => setSelectedCampaignLibraryGroupIds(allSelected ? [] : allLibraryGroupIds)}
              disabled={groups.length === 0}
              className="text-[10px] text-blue-600 hover:text-blue-700 font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {allSelected ? "取消全选" : "全选"}
            </button>
          </div>
        </div>

        <div className="border border-slate-200 rounded-xl p-2 bg-slate-50/40 max-h-[330px] overflow-y-auto flex flex-col gap-1.5">
          {groups.length === 0 ? (
            <div className="text-[10px] text-slate-400 text-center py-10">
              群组库暂无数据，请先到“群组维护”页面同步或添加群组。
            </div>
          ) : (
            groups.map(g => {
              const isChecked = selectedCampaignLibraryGroupIds.includes(g.id);
              const displayUsername = g.username ? (g.username.startsWith('@') ? g.username : `@${g.username}`) : g.id;
              const isDisabled = !g.enabled;

              return (
                <label
                  key={g.id}
                  className={`flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg border text-xs select-none transition-colors ${
                    isDisabled
                      ? 'bg-slate-50 border-slate-100 text-slate-300 cursor-not-allowed'
                      :
                    isChecked
                      ? 'bg-blue-50/40 border-blue-100 text-blue-900'
                      : 'bg-white border-slate-100 hover:bg-slate-50 text-slate-700 cursor-pointer'
                  }`}
                >
                  <div className="flex items-center gap-2 overflow-hidden min-w-0">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      disabled={isDisabled}
                      onChange={(e) => {
                        if (isDisabled) return;
                        if (e.target.checked) {
                          setSelectedCampaignLibraryGroupIds(prev => prev.includes(g.id) ? prev : [...prev, g.id]);
                        } else {
                          setSelectedCampaignLibraryGroupIds(prev => prev.filter(id => id !== g.id));
                        }
                      }}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-3.5 h-3.5 flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
                    />
                    <div className="flex flex-col gap-0.5 overflow-hidden min-w-0">
                      <span className="font-semibold truncate">{g.title || '未命名群组'}</span>
                      <span className="text-[10px] text-slate-400 font-mono truncate">{displayUsername}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0 text-[9px] text-slate-400">
                    {isDisabled && <span className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-400">已禁用</span>}
                    {g.category && <span className="px-1.5 py-0.5 bg-slate-100 rounded">{g.category}</span>}
                    {g.memberCount ? <span className="font-mono">{g.memberCount.toLocaleString()}人</span> : null}
                  </div>
                </label>
              );
            })
          )}
        </div>

        <p className="text-[10px] text-slate-400 leading-relaxed">
          * 多账号安全轰炸会先判断账号是否已在目标群；未加入的账号只先加入准备，不会立刻发广告。
        </p>
      </div>
    );
  };

  if (!isLoggedIn) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-100 font-sans overflow-hidden relative">
        {/* Background Decorative Gradients */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0">
          <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[70%] bg-blue-400/10 rounded-full blur-3xl"></div>
          <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[70%] bg-purple-400/10 rounded-full blur-3xl"></div>
        </div>

        {/* Auth Card Box */}
        <div className="w-full max-w-md bg-white/80 backdrop-blur-md border border-slate-200/50 shadow-2xl rounded-3xl p-8 z-10 mx-4 flex flex-col gap-6 relative">
          
          {/* Logo Brand */}
          <div className="flex flex-col items-center gap-3">
            <div className="text-center">
              <h1 className="text-2xl font-black text-slate-900 tracking-wide">RosePay telegram tools</h1>
              <p className="text-xs text-slate-400 font-light mt-1 tracking-widest uppercase text-center w-full">
                {!isAdminInitialized ? '系统首次运行初始化' : '用户身份登录验证'}
              </p>
            </div>
          </div>

          {!isAdminInitialized ? (
            /* First Run Setup Administrator Form */
            <div className="flex flex-col gap-4">
              <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-3.5 text-xs text-blue-800 leading-normal flex flex-col gap-1">
                <span className="font-bold flex items-center gap-1">
                  <Shield className="w-3.5 h-3.5" /> 首次启动说明
                </span>
                <span>检测到系统中尚未配置任何管理账户。请设定主管理员账号以登录控制台。该管理员将拥有全局最高控制特权。</span>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600">管理员用户名</label>
                <input 
                  type="text" 
                  value={setupUsername}
                  onChange={(e) => setSetupUsername(e.target.value)}
                  placeholder="请输入主管理员用户名"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-sm text-slate-800 focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono transition-all"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600">管理员密码</label>
                <input 
                  type="password" 
                  value={setupPassword}
                  onChange={(e) => setSetupPassword(e.target.value)}
                  placeholder="请输入主管理员密码（不小于6位）"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-sm text-slate-800 focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600">确认管理员密码</label>
                <input 
                  type="password" 
                  value={setupConfirmPassword}
                  onChange={(e) => setSetupConfirmPassword(e.target.value)}
                  placeholder="请再次确认密码"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-sm text-slate-800 focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                />
              </div>

              <button
                onClick={async () => {
                  if (!setupUsername.trim()) {
                    alert("管理员用户名不能为空");
                    return;
                  }
                  if (setupPassword.length < 6) {
                    alert("密码长度不能小于 6 位");
                    return;
                  }
                  if (setupPassword !== setupConfirmPassword) {
                    alert("两次输入的密码不一致");
                    return;
                  }
                  const backendUrl = BASE_URL;
                  try {
                    const res = await fetch(`${backendUrl}/api/auth/setup-admin`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ username: setupUsername.trim(), password: setupPassword })
                    });
                    const data = await res.json();
                    if (res.ok) {
                      setToastText("管理员初始化成功，正在自动登录...");
                      setTimeout(() => setToastText(''), 2000);
                      setIsAdminInitialized(true);
                      setLoginUsername(setupUsername.trim());
                      setLoginPassword(setupPassword);
                      // Auto login
                      setTimeout(() => {
                        handleLoginSubmit();
                      }, 1000);
                    } else {
                      alert(`初始化失败: ${data.detail}`);
                    }
                  } catch (err: any) {
                    alert(`网络请求异常: ${err.message}`);
                  }
                }}
                className="w-full py-3.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-sm shadow-lg shadow-blue-600/10 active:scale-[0.98] transition-all mt-2"
              >
                初始化管理员并登录
              </button>
            </div>
          ) : (
            /* Standard User Login Form */
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600">用户名 (Username)</label>
                <input 
                  type="text" 
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  placeholder="请输入您的用户名"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-sm text-slate-800 focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono transition-all"
                  onKeyDown={(e) => { if (e.key === 'Enter') handleLoginSubmit(); }}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600">登录密码 (Password)</label>
                <input 
                  type="password" 
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="请输入您的登录密码"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-sm text-slate-800 focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                  onKeyDown={(e) => { if (e.key === 'Enter') handleLoginSubmit(); }}
                />
              </div>

              <button
                onClick={handleLoginSubmit}
                className="w-full py-3.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-sm shadow-lg shadow-blue-600/10 active:scale-[0.98] transition-all mt-2"
              >
                登 录
              </button>
            </div>
          )}

        {showDeepSeekConfigModal && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
              
              {/* Header */}
              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <div>
                  <h3 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                    <Key className="w-4 h-4 text-cyan-600" />
                    配置 DeepSeek API 密钥
                  </h3>
                  <p className="text-[10px] text-slate-400 mt-0.5">配置您的 DeepSeek API Key，用于智能搜群时的消息分析。</p>
                </div>
                <button
                  onClick={() => setShowDeepSeekConfigModal(false)}
                  className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Body */}
              <div className="p-5 flex flex-col gap-4 text-xs">
                <div className="flex flex-col gap-1.5">
                  <label className="font-semibold text-slate-500">API 密钥 (API Key)</label>
                  <input
                    type="password"
                    value={newDeepSeekKey}
                    onChange={(e) => setNewDeepSeekKey(e.target.value)}
                    placeholder="输入 DeepSeek API Key..."
                    className="w-full text-xs bg-slate-50 border border-slate-100 rounded-xl px-3 py-2.5 focus:outline-none focus:border-cyan-500 focus:bg-white transition-all font-mono"
                  />
                  <span className="text-[10px] text-slate-400 mt-1 leading-normal">
                    如果您没有密钥，可前往 <a href="https://platform.deepseek.com/" target="_blank" rel="noopener noreferrer" className="text-cyan-600 hover:underline font-bold">DeepSeek 开放平台</a> 注册充值获取。
                  </span>
                </div>
              </div>

              {/* Footer */}
              <div className="p-5 border-t border-slate-100 flex justify-end gap-3 bg-slate-50/50">
                <button
                  onClick={() => setShowDeepSeekConfigModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-all"
                >
                  取消
                </button>
                <button
                  onClick={saveDeepSeekKey}
                  disabled={savingDeepSeekKey || !newDeepSeekKey.trim()}
                  className="px-4 py-2 text-xs font-semibold text-white bg-cyan-600 hover:bg-cyan-700 disabled:bg-cyan-300 rounded-lg transition-all shadow-sm flex items-center gap-1"
                >
                  {savingDeepSeekKey ? '正在保存...' : '💾 保存配置'}
                </button>
              </div>

            </div>
          </div>
        )}
        </div>
      </div>
    );
  }


  return (

    <div className="flex h-screen bg-slate-50 text-slate-800 font-sans overflow-hidden">

      

      {/* 1. LEFT SIDEBAR PANEL */}

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside className={`fixed lg:static inset-y-0 left-0 w-64 bg-white border-r border-slate-100 flex flex-col justify-between h-full z-30 shrink-0 transition-transform duration-300 transform lg:transform-none ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        
        {/* Brand Logo Header */}
        <div className="p-6 border-b border-slate-50 flex items-center justify-between gap-3">
          <div>
            <h1 className="font-bold text-slate-900 tracking-wide text-base leading-none">RosePay telegram tools</h1>
          </div>
          {/* Close button on mobile */}
          <button 
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1.5 hover:bg-slate-50 text-slate-400 hover:text-slate-600 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>



        {/* Sidebar Navigation Menus */}

        <nav className="flex-grow py-6 px-4 flex flex-col gap-1.5 overflow-y-auto">

          {allowedTabs.includes('login') && (

            <button 

              onClick={() => setActiveTab('login')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'login' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <UserCheck className="w-4 h-4 shrink-0" />

              <span>账号登录</span>

            </button>

          )}



          {allowedTabs.includes('accounts') && (

            <button 

              onClick={() => setActiveTab('accounts')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'accounts' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <User className="w-4 h-4 shrink-0" />

              <span>账号管理</span>

            </button>

          )}



          {allowedTabs.includes('groups') && (

            <button 

              onClick={() => setActiveTab('groups')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'groups' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <Users className="w-4 h-4 shrink-0" />

              <span>群组维护</span>

            </button>

          )}



          {allowedTabs.includes('join') && (

            <button 

              onClick={() => setActiveTab('join')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'join' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <PlusCircle className="w-4 h-4 shrink-0" />

              <span>自动入群</span>

            </button>

          )}



          {allowedTabs.includes('campaign') && (

            <button 

              onClick={() => setActiveTab('campaign')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'campaign' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <MessageSquare className="w-4 h-4 shrink-0" />

              <span>轰炸他们</span>

            </button>

          )}



          {allowedTabs.includes('templates') && (

            <button 

              onClick={() => setActiveTab('templates')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'templates' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <FileCheck className="w-4 h-4 shrink-0" />

              <span>广告内容</span>

            </button>

          )}



          {allowedTabs.includes('logs') && (

            <button 

              onClick={() => setActiveTab('logs')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'logs' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <FileText className="w-4 h-4 shrink-0" />

              <span>任务日志</span>

            </button>

          )}



          {allowedTabs.includes('finder') && (

            <button 

              onClick={() => setActiveTab('finder')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'finder' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <Search className="w-4 h-4 shrink-0" />

              <span>智能搜群</span>

            </button>

          )}



          {allowedTabs.includes('expansion') && (

            <button 

              onClick={() => setActiveTab('expansion')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'expansion' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <Compass className="w-4 h-4 shrink-0" />

              <span>业务拓展</span>

            </button>

          )}


          {allowedTabs.includes('settings') && (

            <button 

              onClick={() => setActiveTab('settings')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'settings' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <Settings className="w-4 h-4 shrink-0" />

              <span>设置</span>

            </button>

          )}



          {allowedTabs.includes('users') && (

            <button 

              onClick={() => setActiveTab('users')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'users' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <Shield className="w-4 h-4 shrink-0" />

              <span>系统管理</span>

            </button>

          )}




          {(allowedTabs.includes('bot_auth') || allowedTabs.includes('bots') || userRole === 'admin') && (

            <button 

              onClick={() => setActiveTab('bot_auth')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'bot_auth' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <Bot className="w-4 h-4 shrink-0 text-amber-500" />

              <span>Bot 权限管理</span>

            </button>

          )}



          {allowedTabs.includes('permissions') && (

            <button 

              onClick={() => setActiveTab('permissions')}

              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 border-l-4 ${

                activeTab === 'permissions' 

                  ? 'bg-blue-50/50 text-blue-600 border-blue-500 font-semibold' 

                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border-transparent'

              }`}

            >

              <Shield className="w-4 h-4 shrink-0" />

              <span>权限管理</span>

            </button>

          )}

        </nav>





      </aside>



      {/* 2. RIGHT MAIN CONTENT PANEL */}

      <main className="flex-grow flex flex-col h-full overflow-hidden relative">

        

        {/* RIGHT TOP HEADER BAR */}

        <header className="h-20 bg-white border-b border-slate-100 px-4 lg:px-8 flex items-center justify-between z-20 shrink-0">

          <div className="flex items-center gap-3">
            {/* Hamburger button on mobile */}
            <button 
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 hover:bg-slate-50 text-slate-500 hover:text-slate-800 rounded-xl transition-all border border-slate-100 flex items-center justify-center"
            >
              <Menu className="w-5 h-5" />
            </button>

            <div>

              <h2 className="text-base lg:text-xl font-bold text-slate-900">

                {activeTab === 'login' && '账号登录'}

                {activeTab === 'accounts' && '账号管理'}

                {activeTab === 'groups' && '群组维护'}

                {activeTab === 'join' && '自动入群'}

                {activeTab === 'campaign' && '轰炸他们'}

                {activeTab === 'templates' && '广告内容'}

                {activeTab === 'scraper' && '接码辅助'}

                {activeTab === 'logs' && '任务日志'}

                {activeTab === 'settings' && '设置'}

                {activeTab === 'users' && '系统管理'}

                {activeTab === 'permissions' && '权限管理'}

                {activeTab === 'bot_auth' && 'Bot 权限管理'}

              </h2>

              <p className="hidden md:block text-xs text-slate-400 font-light mt-0.5">

                {activeTab === 'login' && '导入账号资料，按人工登录步骤跟踪状态。'}

                {activeTab === 'accounts' && '查看和维护系统中已登录 and 已配置的 Telegram 账号信息。'}

                {activeTab === 'groups' && '同步聊天文件夹的群组，管理广告群组状态。'}

                {activeTab === 'join' && '全自动控制登录账号加入指定的群组链接列表。'}

                {activeTab === 'campaign' && '在后台批量运行文件夹群发的任务。'}

                {activeTab === 'templates' && '维护和管理预设的广告词词库。'}

                {activeTab === 'scraper' && '手动提取并实时查看接码网页生成的设备验证码与两步验证 (2FA) 密码。'}

                {activeTab === 'logs' && '实时轮询查看当前的发送明细日志。'}

                {activeTab === 'settings' && '配置 Telegram 账号的代理与连接选项参数。'}

                {activeTab === 'users' && '配置不同的系统用户，为操作员分配对应的管理权限。'}

                {activeTab === 'permissions' && '配置各角色在系统中能访问的页面范围。'}

                {activeTab === 'bot_auth' && '管理 AI Bot 与翻译 Bot 的授权账号、角色和自动回复模板。'}

              </p>

            </div>
          </div>



          {/* Top Status & Controls */}

          <div className="flex items-center gap-3">

            {isLoggedIn && (

              <div className="flex items-center gap-2 border-r border-slate-200 pr-4 py-1">

                <span className="text-xs font-semibold text-slate-600 flex items-center gap-1">

                  <User className="w-3.5 h-3.5 text-blue-500" />

                  {currentUsername} ({userRole === 'admin' ? '管理员' : '操作员'})

                </span>

                <button 

                  onClick={() => {
                    localStorage.removeItem('rosepay_auth_token');
                    sessionStorage.removeItem('rosepay_auth_token');
                    setIsLoggedIn(false);
                    setUserRole(null);
                    setCurrentUsername('');
                    setAccountViewScope('mine');
                    setToastText('已退出登录');
                    setTimeout(() => {
                      window.location.reload();
                    }, 500);
                  }}

                  className="px-2.5 py-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 text-xs font-semibold transition-colors"

                >

                  退出

                </button>

              </div>

            )}



            <button 

              onClick={() => {

                setToastText('已刷新数据状态');

                setTimeout(() => setToastText(''), 2500);

              }}

              className="p-2 border border-slate-200 hover:border-slate-300 rounded-lg text-slate-500 hover:text-slate-800 bg-white transition-all shadow-sm"

              title="刷新当前数据"

            >

              <RefreshCw className="w-4 h-4" />

            </button>

          </div>

        </header>



        {/* MAIN PANEL CONTENT PORTPORT */}

        <div className="flex-grow p-4 lg:p-8 overflow-y-auto flex flex-col gap-6">

          

          {/* A. Tab-Specific Metrics Dashboard Panel */}

          {activeTab !== 'login' && activeTab !== 'settings' && activeTab !== 'users' && (

            <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 shrink-0">

              {activeTab === 'accounts' && (

                <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm">

                  <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">账号数量</div>

                  <div className="text-3xl font-bold text-slate-900 mt-2 font-mono">{backendAccounts.length}</div>

                </div>

              )}



              {activeTab === 'groups' && (

                <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm">

                  <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">群组链接</div>

                  <div className="text-3xl font-bold text-slate-900 mt-2 font-mono">{groups.length}</div>

                </div>

              )}



              {activeTab === 'join' && (

                <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm">

                  <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">入群任务</div>

                  <div className="text-3xl font-bold text-slate-900 mt-2 font-mono flex items-center gap-2">

                    <span className={`w-3.5 h-3.5 rounded-full ${joinRunning ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'}`}></span>

                    <span className="text-lg font-semibold">{joinRunning ? '运行中' : '空闲'}</span>

                  </div>

                </div>

              )}



              {activeTab === 'campaign' && (

                <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm">

                  <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">群发任务</div>

                  <div className="text-3xl font-bold text-slate-900 mt-2 font-mono flex items-center gap-2">

                    <span className={`w-3.5 h-3.5 rounded-full ${campaignTasks.some(t => t.status === 'running') ? 'bg-emerald-500 animate-pulse' : 'bg-amber-400'}`}></span>

                    <span className="text-lg font-semibold">{campaignTasks.some(t => t.status === 'running') ? '运行中' : '暂停'}</span>

                  </div>

                </div>

              )}



          {activeTab === 'logs' && (
            <div className="bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden flex flex-col">
              <div className="p-6 border-b border-slate-50 bg-slate-50/20 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                <div>
                  <h3 className="font-bold text-slate-900 text-base">系统及群发日志明细</h3>
                  <p className="text-xs text-slate-400 mt-0.5">查看各个群发轰炸任务的执行细节</p>
                </div>
                
                <div className="flex flex-wrap gap-2.5 items-center">
                  <span className="text-xs font-bold text-slate-600">选择群发任务：</span>
                  <select
                    value={selectedLogTaskId}
                    onChange={(e) => setSelectedLogTaskId(e.target.value)}
                    className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-2 text-xs font-bold text-slate-700 focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 max-w-xs transition-all cursor-pointer"
                  >
                    {campaignTasks.length === 0 && (
                      <option value="">暂无轰炸任务记录</option>
                    )}
                    {groupCampaignTasks(campaignTasks).map((task) => (
                      <option key={task.id} value={task.id}>
                        任务 #{task.id.substring(0, 8)} ({task.created_at}) - 账号: {task.phones.join(', ')} (成功: {task.success_count})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="p-6 flex flex-col gap-3 font-mono text-xs">
                {!selectedLogTaskId ? (
                  <div className="text-slate-400 text-center py-12">暂无群发任务记录，请先在“轰炸他们”页面创建并启动任务。</div>
                ) : selectedTaskLogs.length === 0 ? (
                  <div className="text-slate-400 text-center py-12">当前任务暂无发送明细日志。</div>
                ) : (
                  selectedTaskLogs.map((log, index) => (
                    <div key={index} className="flex gap-4 p-4 border border-slate-100 rounded-xl hover:border-slate-200 shadow-sm transition-all bg-slate-50/10">
                      <div className="text-slate-400 font-semibold">{log.timestamp}</div>
                      <div className="w-20">
                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-[9px] font-semibold border border-blue-100">
                          第 {log.cycle} 轮
                        </span>
                      </div>
                      <div className="flex-grow">
                        <div className="font-semibold text-slate-800">发送到群组：{log.group_title}</div>
                        <div className="text-slate-500 mt-0.5 font-mono text-[10px]">
                          账号: {log.phone || '-'} | 群组ID: {log.group_id} | 详情: {log.detail}
                        </div>
                      </div>
                      <div>
                        <span className={`px-2.5 py-0.5 rounded text-[10px] font-semibold ${
                          log.status === 'success' 
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' 
                            : 'bg-rose-50 text-rose-700 border border-rose-100'
                        }`}>
                          {log.status === 'success' ? '成功' : '失败'}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

            </section>

          )}



          {/* B. Dynamic Tab Content View */}

          

          {/* TAB 1: ACCOUNT LOGIN CONSOLE */}

          {activeTab === 'login' && (

            <div className="bg-white border border-slate-100 rounded-2xl shadow-sm flex flex-col min-w-0 overflow-hidden">

              <div className="p-6 border-b border-slate-50 flex justify-between items-center bg-slate-50/20">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">批量登录账号</h3>

                  <p className="text-xs text-slate-400 mt-0.5">支持批量输入账号配置进行登录与校验</p>

                </div>

              </div>



              <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-8">

                

                {/* Left Column: Input Textarea */}

                <div className="flex flex-col gap-4">

                  <div className="flex flex-col gap-2">

                    <label className="text-sm font-semibold text-slate-700">账号列表</label>

                    <textarea 

                      value={textareaValue}

                      onChange={(e) => setTextareaValue(e.target.value)}

                      placeholder="请输入手机号（例如：+919083791809），每行一个"

                      className="w-full h-48 bg-slate-50/60 border border-slate-200 rounded-xl p-4 font-mono text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 resize-none transition-all"

                    ></textarea>

                  </div>

                  

                  <button 

                    onClick={handleImportAccounts}

                    className="w-full sm:w-auto self-start px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-sm shadow-md shadow-blue-600/10 transition-all active:scale-[0.98]"

                  >

                    导入账号

                  </button>

                </div>



                {/* Right Column: Account Pool rendering */}

                <div className="flex flex-col gap-4">

                  <div className="flex justify-between items-center">

                    <label className="text-sm font-semibold text-slate-700">当前账号池</label>

                    {accountsPool.length > 0 && (

                      <button 

                        onClick={handleBatchLoginAll}

                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-sm transition-all active:scale-[0.98]"

                      >

                        ⚡ 一键批量登录

                      </button>

                    )}

                  </div>

                  

                  <div className="flex-grow h-48 overflow-y-auto border border-slate-100 rounded-xl p-4 flex flex-col gap-4 bg-slate-50/20">

                    {accountsPool.filter(acc => acc.status !== 'success').length === 0 ? (

                      <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">

                        <UserCheck className="w-10 h-10 opacity-30" />

                        <span className="text-xs font-light">账号池目前没有需要登录的账号。</span>

                      </div>

                    ) : (

                      accountsPool.map((account) => {

                        if (account.status === 'success') return null;

                        return (

                          <div key={account.accountId} className="bg-white border border-slate-100 rounded-xl p-4 shadow-sm flex flex-col gap-3.5 relative hover:shadow-md transition-all">

                            

                            {/* Card Header: Phone number and Delete button */}

                            <div className="flex justify-between items-center">

                              <div className="flex items-center gap-2">

                                <span className="font-bold text-slate-900 font-mono text-sm">{account.phone}</span>

                              </div>

                              

                              <div className="flex items-center gap-2">

                                {/* Current status tag */}

                                <span className={`px-2 py-0.5 rounded text-[10px] font-semibold tracking-wide border ${

                                  account.status === 'failed' 

                                    ? 'bg-rose-50 text-rose-700 border-rose-100'

                                    : account.status === '2fa_required'

                                    ? 'bg-amber-50 text-amber-700 border-amber-100 animate-pulse'

                                    : 'bg-blue-50 text-blue-700 border-blue-100'

                                }`}>

                                  {account.status === 'idle' && '待登录'}

                                  {account.status === 'sending_code' && '发送手机号中'}

                                  {account.status === 'waiting_code' && '等待验证码'}

                                  {account.status === 'fetching_code' && '自动接码中'}

                                  {account.status === 'submitting_code' && '登录验证中'}

                                  {account.status === '2fa_required' && '需要2FA密码'}

                                  {account.status === 'failed' && '登录失败'}

                                </span>

                                

                                <button 

                                  onClick={() => handleDeleteAccount(account.accountId)}

                                  className="w-6 h-6 hover:bg-rose-50 rounded-full flex items-center justify-center text-slate-400 hover:text-rose-600 transition-colors"

                                  title="删除账号"

                                >

                                  <X className="w-3.5 h-3.5" />

                                </button>

                              </div>

                            </div>



                            {/* Progress Tracker Status Text */}

                            <div className="bg-slate-50 rounded-lg p-2.5 border border-slate-100 flex flex-col gap-1.5">

                              <div className="text-[11px] text-slate-500 font-medium leading-normal">

                                {account.statusText || '已就绪，等待自动接码登录'}

                              </div>

                              

                              {/* Scraped Code & Default 2FA display */}

                              {(account.code || account.defaultPass2fa) && (

                                <div className="grid grid-cols-2 gap-2 mt-1 border-t border-slate-200/50 pt-1.5 text-[10px] text-slate-400 font-mono">

                                  <div>验证码: <span className="text-slate-800 font-semibold">{account.code || '未获取'}</span></div>

                                  <div>默认2FA: <span className="text-slate-800 font-semibold">{account.defaultPass2fa || '无'}</span></div>

                                </div>

                              )}

                            </div>



                            {/* Conditional Manual 2FA Input and Submit Button */}

                            {account.showManual2fa && (

                              <div className="bg-amber-50/30 border border-amber-100 rounded-lg p-3 flex flex-col gap-2.5 transition-all">

                                <div className="text-[11px] text-amber-800 font-medium">

                                  🔒 检测到需要二步验证。网页密码不对（可能已被手动修改），请在此输入 2FA 密码：

                                </div>

                                

                                <div className="flex gap-2">

                                  <input 

                                    type="password" 

                                    value={account.pass2fa}

                                    onChange={(e) => handleUpdatePass2fa(account.accountId, e.target.value)}

                                    placeholder="请输入手动修改后的 2FA 密码"

                                    className="flex-grow bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"

                                  />

                                  <button

                                    onClick={() => submit2FAFlow(account.accountId)}

                                    disabled={account.status === 'submitting_code'}

                                    className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-xs font-bold rounded-lg transition-all active:scale-[0.98] shadow-sm shrink-0"

                                  >

                                    {account.status === 'submitting_code' ? '验证中...' : '登录'}

                                  </button>

                                </div>

                              </div>

                            )}



                            <div className="flex gap-2 justify-end border-t border-slate-50 pt-2.5">

                              {/* If waiting for code manually or automatic fetching fails, allow manual code entry override */}

                              {(account.status === 'waiting_code' || account.status === 'failed') && (

                                <div className="flex-grow flex gap-1.5 items-center">

                                  <input 

                                    type="text" 

                                    value={account.code}

                                    onChange={(e) => handleUpdateCode(account.accountId, e.target.value)}

                                    placeholder="手动验证码"

                                    className="w-24 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-blue-500 font-mono"

                                  />

                                  <button

                                    onClick={() => submitManualCodeFlow(account.accountId)}

                                    disabled={(account.status as string) === 'submitting_code'}

                                    className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 disabled:bg-slate-50 text-slate-700 text-xs font-bold rounded-lg transition-all active:scale-[0.98] shrink-0"

                                    title="手动提交验证码登录"

                                  >

                                    登录

                                  </button>

                                </div>

                              )}

                              

                              <button 

                                onClick={() => startLoginFlow(account.accountId)}

                                disabled={

                                  account.status === 'sending_code' || 

                                  account.status === 'fetching_code' || 

                                  account.status === 'submitting_code'

                                }

                                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-xs font-bold rounded-lg transition-all active:scale-[0.98] shadow-sm"

                              >

                                {account.status === 'sending_code' && '正在发送...'}

                                {account.status === 'fetching_code' && '正在接码...'}

                                {account.status === 'submitting_code' && '正在登录...'}

                                {account.status === 'idle' && '开始自动接码登录'}

                                {account.status === 'waiting_code' && '重新自动接码'}

                                {account.status === '2fa_required' && '重试自动登录'}

                                {account.status === 'failed' && '重新尝试登录'}

                              </button>

                            </div>



                          </div>

                        );

                      })

                    )}

                  </div>

                </div>



              </div>



              {/* Tips panel & help text */}

              <div className="p-6 border-t border-slate-50 bg-slate-50/10 flex items-start gap-3">

                <HelpCircle className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />

                <p className="text-xs text-slate-500 leading-relaxed font-light">

                  每一行一个手机号。请在 Telegram 客户端完成手机号提交后，在右侧填写收到的验证码并更新状态。

                </p>

              </div>

            </div>

          )}



          {/* TAB 7: ACCOUNTS MANAGEMENT */}

          {activeTab === 'accounts' && (

            <div className="bg-white border border-slate-100 rounded-2xl shadow-sm flex flex-col">

              <div className="p-6 border-b border-slate-50 bg-slate-50/20 flex justify-between items-center">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">登录账号管理</h3>

                </div>

                <div className="flex gap-2">

                  {isBatchManagingAccounts ? (

                    <>

                      <button 

                        onClick={() => {

                          const allFiltered = getFilteredAndSortedAccounts();

                          const unmodifiedIds = allFiltered.filter(acc => !acc.config?.profile_modified).map(acc => acc.id);

                          setSelectedAccountIds(unmodifiedIds);

                        }}

                        className="px-4 py-2 bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 rounded-lg text-xs font-bold shadow-sm transition-all"

                      >

                        全选所有未修改账号

                      </button>

                      <button 

                        onClick={() => {

                          setIsBatchManagingAccounts(false);

                          setSelectedAccountIds([]);

                        }}

                        className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg text-xs font-bold shadow-sm transition-all"

                      >

                        退出管理

                      </button>

                    </>

                  ) : (

                    <>

                      <button 

                        onClick={() => {

                          setIsBatchManagingAccounts(true);

                          setSelectedAccountIds([]);

                        }}

                        className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-bold shadow-sm transition-all"

                      >

                        ⚙️ 批量管理

                      </button>

                      <button 

                        onClick={() => {

                          fetchAvatarLibrary();

                          setShowLibraryManager(true);

                        }}

                        className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-bold shadow-sm transition-all flex items-center gap-1.5"

                      >

                        <Image className="w-3.5 h-3.5" />

                        <span>🖼️ 头像库管理</span>

                      </button>

                      <button 

                        onClick={() => {

                          fetchLoginLogs();

                          setShowLoginLogsModal(true);

                        }}

                        className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-bold shadow-sm transition-all flex items-center gap-1.5"

                      >

                        <FileText className="w-3.5 h-3.5" />

                        <span>📝 登录记录</span>

                      </button>

                      <button 

                        onClick={() => fetchBackendAccounts(true)}

                        disabled={loadingAccounts}

                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-xs font-bold shadow-sm transition-all flex items-center gap-1.5"

                      >

                        <RefreshCw className={`w-3.5 h-3.5 ${loadingAccounts ? 'animate-spin' : ''}`} />

                        <span>刷新账号列表</span>

                      </button>

                      <button 

                        onClick={togglePrivateRelayListeners}

                        disabled={privateRelayStarting}

                        className={`px-4 py-2 rounded-lg text-xs font-bold shadow-sm transition-all flex items-center gap-1.5 border ${
                          privateRelayActive
                            ? 'bg-emerald-50 hover:bg-emerald-100 disabled:bg-emerald-50 disabled:text-emerald-400 text-emerald-700 border-emerald-200'
                            : 'bg-cyan-50 hover:bg-cyan-100 disabled:bg-cyan-50 disabled:text-cyan-400 text-cyan-700 border-cyan-200'
                        }`}

                        title={privateRelayActive ? '关闭当前私聊中转监听，不删除任何 session 或数据。' : '启动所有可用且空闲账号的实时私聊监听；收到私聊后由 AI Bot 转发到中转群主题。'}

                      >

                        {privateRelayStarting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Bell className="w-3.5 h-3.5" />}

                        <span>{privateRelayStarting ? (privateRelayActive ? '正在关闭中转' : '正在启动中转') : (privateRelayActive ? '关闭私聊中转' : '启动私聊中转')}</span>

                      </button>

                    </>

                  )}

                </div>

              </div>



              {/* Accounts list rendering */}

              {loadingAccounts && backendAccounts.length === 0 ? (

                <div className="p-6 flex flex-col items-center justify-center py-12 text-slate-400 gap-2">

                  <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />

                  <span className="text-xs font-light">正在加载账号列表...</span>

                </div>

              ) : backendAccounts.length === 0 ? (

                <div className="p-6">

                  <div className="flex flex-col items-center justify-center py-12 text-slate-400 gap-2 border border-dashed border-slate-200 rounded-xl bg-slate-50/20">

                    <UserCheck className="w-10 h-10 opacity-30" />

                    <span className="text-xs font-light">暂无已配置账号，请在 “账号登录” 页面导入账号并登录。</span>

                  </div>

                </div>

              ) : (

                <>

                  {/* Search and Sort controls */}

                  <div className="px-6 py-4 border-b border-slate-100 flex flex-col sm:flex-row gap-4 justify-between items-center bg-slate-50/5">

                    <div className="relative w-full sm:max-w-xs">

                      <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">

                        <Search className="h-4 w-4 text-slate-400" />

                      </span>

                      <input

                        type="text"

                        value={accountSearchQuery}

                        onChange={(e) => setAccountSearchQuery(e.target.value)}

                        placeholder="输入号码、名字模糊搜索账户..."

                        className="block w-full pl-9 pr-4 py-2 text-xs border border-slate-200 rounded-lg bg-white placeholder-slate-400 text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all shadow-sm"

                      />

                    </div>

                    <div className="flex items-center gap-3 text-xs text-slate-500 self-end sm:self-auto select-none flex-wrap justify-end">

                      <div className="inline-flex items-center rounded-lg border border-slate-200 bg-white p-0.5 shadow-xs">
                        {([
                          { id: 'mine' as const, label: '我的账号' },
                          { id: 'all' as const, label: userRole === 'admin' ? '全部账号' : '本公司账号' }
                        ]).map(option => (
                          <label
                            key={option.id}
                            className={`px-2.5 py-1 rounded-md text-[11px] font-bold cursor-pointer transition-all ${
                              accountViewScope === option.id
                                ? 'bg-blue-50 text-blue-700'
                                : 'text-slate-500 hover:text-slate-700'
                            }`}
                            title={option.id === 'mine' ? '只显示归属于当前登录用户的账号' : (userRole === 'admin' ? '管理员查看全部账号，但私聊弹框仍只提醒自己的账号' : '显示当前公司内的账号')}
                          >
                            <input
                              type="radio"
                              name="account-view-scope"
                              className="sr-only"
                              checked={accountViewScope === option.id}
                              onChange={() => {
                                setAccountViewScope(option.id);
                                fetchBackendAccounts(false, option.id);
                                fetchPrivateUnreadSummary(false, option.id);
                              }}
                            />
                            {option.label}
                          </label>
                        ))}
                      </div>

                      <span>排序方式：</span>

                      <button

                        onClick={() => {

                          if (accountSortField === 'health') {

                            setAccountSortDesc(!accountSortDesc);

                          } else {

                            setAccountSortField('health');

                            setAccountSortDesc(true);

                          }

                        }}

                        className="px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 font-bold transition-all flex items-center gap-1.5"

                      >

                        <span>健康评分 ({accountSortDesc ? '从高到低 ⬇️' : '从低到高 ⬆️'})</span>

                      </button>

                    </div>

                  </div>



                  {(() => {

                    const filtered = getFilteredAndSortedAccounts();

                    if (filtered.length === 0) {

                      return (

                        <div className="p-6">

                          <div className="flex flex-col items-center justify-center py-12 text-slate-400 gap-2 border border-dashed border-slate-200 rounded-xl bg-slate-50/20">

                            <Search className="w-10 h-10 opacity-30 animate-pulse" />

                            <span className="text-xs font-light">没有找到匹配的账号。</span>

                          </div>

                        </div>

                      );

                    }

                    return (

                      <div className="w-full max-w-full overflow-x-auto account-management-table-wrap">

                        <table className="account-management-table w-full table-auto text-left border-collapse">
                          <thead>
                            <tr className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-semibold uppercase text-slate-400 tracking-wider">
                              {isBatchManagingAccounts && (
                                <th className="py-4 px-3 w-12 text-center">
                                  <input 
                                    type="checkbox" 
                                    checked={filtered.some(acc => !isAccountLockedForManualOperation(acc)) && selectedAccountIds.length === filtered.filter(acc => !isAccountLockedForManualOperation(acc)).length}
                                    onChange={() => handleToggleSelectAllAccounts(filtered.map(acc => acc.id))}
                                    className="rounded text-blue-600 focus:ring-blue-500/20 border-slate-300 cursor-pointer"
                                  />
                                </th>
                              )}
                              <th className="py-2.5 px-2 text-xs w-[15%]">账号</th>
                              <th className="py-2.5 px-2 text-xs w-[14%]">归属 / 创建者</th>
                              <th className="py-2.5 px-2 text-xs w-[9%]">连接 & 登录</th>
                              <th 
                                className="py-2.5 px-2 text-xs cursor-pointer hover:bg-slate-100/60 select-none transition-colors w-[8%]"
                                onClick={() => {
                                  if (accountSortField === 'available') {
                                    setAccountSortDesc(!accountSortDesc);
                                  } else {
                                    setAccountSortField('available');
                                    setAccountSortDesc(true);
                                  }
                                }}
                              >
                                可用状态 {accountSortField === 'available' && (accountSortDesc ? '⬇️' : '⬆️')}
                              </th>
                              <th className="py-2.5 px-2 text-xs w-[11%]">网络代理</th>
                              <th className="py-2.5 px-2 text-xs w-[8%]">资料</th>
                              <th 
                                className="py-2.5 px-2 text-xs cursor-pointer hover:bg-slate-100/60 select-none transition-colors w-[10%]"
                                onClick={() => {
                                  if (accountSortField === 'health') {
                                    setAccountSortDesc(!accountSortDesc);
                                  } else {
                                    setAccountSortField('health');
                                    setAccountSortDesc(true);
                                  }
                                }}
                              >
                                评分 {accountSortField === 'health' && (accountSortDesc ? '⬇️' : '⬆️')}
                              </th>
                              <th className="py-2.5 px-2 text-xs text-right w-[16%]">操作</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filtered.map((acc) => (
                              <tr 
                                key={acc.id} 
                                onClick={() => {
                                  if (isBatchManagingAccounts) {
                                    handleToggleSelectAccount(acc.id);
                                  }
                                }}
                                className={`border-b border-slate-50 text-sm text-slate-700 hover:bg-slate-50/40 transition-colors ${
                                  isBatchManagingAccounts ? 'cursor-pointer select-none bg-slate-50/10' : ''
                                } ${
                                  isBatchManagingAccounts && selectedAccountIds.includes(acc.id) ? '!bg-blue-50/30' : ''
                                }`}
                              >
                                {isBatchManagingAccounts && (
                                  <td className="py-4 px-3 w-12 text-center" onClick={(e) => e.stopPropagation()}>
                                    <input 
                                      type="checkbox" 
                                      checked={selectedAccountIds.includes(acc.id)}
                                      disabled={isAccountLockedForManualOperation(acc)}
                                      onChange={() => handleToggleSelectAccount(acc.id)}
                                      title={getAccountTaskStateLabel(acc) || '选择账号'}
                                      className="rounded text-blue-600 focus:ring-blue-500/20 border-slate-300 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                                    />
                                  </td>
                                )}
                                <td className="py-2.5 px-2 whitespace-nowrap">
                                  <div className="font-bold text-slate-900 font-mono text-sm truncate" title={acc.name}>{acc.name}</div>
                                  <div className="text-[11px] text-blue-500 font-mono mt-0.5 select-all truncate">
                                    {(() => {
                                      let t = acc.config?.profile_modified_username;
                                      if (t && t.trim()) {
                                        let e = t.trim().replace("@", "");
                                        if (e) return `@${e}`;
                                      }
                                      if (acc.meInfo) {
                                        let t = acc.meInfo.match(/@([a-zA-Z0-9_]+)/);
                                        if (t) return `@${t[1]}`;
                                      }
                                      return "未设置";
                                    })()}
                                  </div>
                                  <div className="text-[10px] text-slate-400 font-mono mt-0.5 truncate">
                                    手机号: +{acc.id}
                                  </div>
                                </td>
                                <td className="py-2.5 px-2 whitespace-nowrap">
                                  <div className="flex flex-col gap-1.5 select-none font-mono text-[11px] min-w-0">
                                    <div className="flex items-center gap-1.5">
                                      <span className="w-12 text-slate-400 font-normal inline-block text-left">归属:</span>
                                      <select
                                        value={acc.config?.owner_username || acc.created_by || acc.config?.created_by || 'rosepay'}
                                        onChange={async (t) => { await handleSetAccountOwner(acc.id, t.target.value); }}
                                        disabled={isAccountLockedForManualOperation(acc)}
                                        title={getAccountTaskStateLabel(acc) || '修改账号归属'}
                                        className="account-owner-select bg-blue-50/80 hover:bg-blue-100/80 disabled:bg-slate-100 disabled:text-slate-400 disabled:border-slate-200 border border-blue-200 text-blue-700 font-bold text-[10px] py-0.5 px-1.5 rounded focus:outline-none focus:ring-1 focus:ring-blue-400 cursor-pointer disabled:cursor-not-allowed transition-all w-[136px] max-w-full"
                                      >
                                        <option value={acc.created_by || acc.config?.created_by || 'rosepay'}>
                                          {acc.created_by || acc.config?.created_by || 'rosepay'} (默认)
                                        </option>
                                        {usersList.map((t) => {
                                          let n = t.username;
                                          return n === (acc.created_by || acc.config?.created_by || 'rosepay') ? null : (
                                            <option key={t.id} value={n}>
                                              {n} {n === currentUsername ? '(我自己)' : ''}
                                            </option>
                                          );
                                        })}
                                        {(() => {
                                          let t = acc.config?.owner_username;
                                          let n = acc.created_by || acc.config?.created_by || 'rosepay';
                                          let r = usersList.some((e) => e.username === t);
                                          return t && t !== n && !r ? (
                                            <option value={t}>{t}</option>
                                          ) : null;
                                        })()}
                                      </select>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                      <span className="w-12 text-slate-400 font-normal inline-block text-left">创建者:</span>
                                      <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-600 font-medium text-[10px] border border-slate-200">
                                        {acc.created_by || acc.config?.created_by || 'rosepay'}
                                      </span>
                                    </div>
                                  </div>
                                </td>
                                <td className="py-2.5 px-2 whitespace-nowrap">
                                  <div className="flex flex-col gap-1">
                                    {acc.is_connected ? (
                                      <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-green-50 text-green-700 border border-green-100 flex items-center gap-1 w-fit">
                                        <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
                                        已连接
                                      </span>
                                    ) : (
                                      <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-slate-50 text-slate-400 border border-slate-200 flex items-center gap-1 w-fit">
                                        <span className="w-1.5 h-1.5 bg-slate-300 rounded-full"></span>
                                        未连接
                                      </span>
                                    )}
                                    {acc.isAuthorized ? (
                                      <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100 flex items-center gap-1 w-fit">
                                        <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></span>
                                        已登录
                                      </span>
                                    ) : (
                                      <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-rose-50 text-rose-700 border border-rose-100 flex items-center gap-1 w-fit">
                                        <span className="w-1.5 h-1.5 bg-rose-500 rounded-full"></span>
                                        未登录
                                      </span>
                                    )}
                                    {acc.private_listener && (
                                      <span
                                        className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-cyan-50 text-cyan-700 border border-cyan-100 flex items-center gap-1 w-fit"
                                        title="空闲账号私聊自动监听中"
                                      >
                                        <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-pulse"></span>
                                        监听中
                                      </span>
                                    )}
                                  </div>
                                </td>
                                <td className="py-2.5 px-2 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                                  {acc.active_operation ? (
                                    <span
                                      className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100 flex items-center gap-1 w-fit cursor-not-allowed select-none"
                                      title={getAccountTaskStateLabel(acc)}
                                    >
                                      <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse"></span>
                                      操作中
                                    </span>
                                  ) : (acc.busy_status && acc.busy_status !== 'idle') ? (
                                    <span
                                      className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-100 flex items-center gap-1 w-fit cursor-not-allowed select-none"
                                      title={getAccountTaskStateLabel(acc)}
                                    >
                                      <span className="w-1.5 h-1.5 bg-amber-500 rounded-full"></span>
                                      占用
                                    </span>
                                  ) : acc.is_available === false ? (
                                    <span
                                      onClick={() => handleToggleAccountAvailableStatus(acc.id)}
                                      className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-50 hover:bg-rose-100 active:scale-[0.97] transition-all text-rose-700 border border-rose-100 flex items-center gap-1 w-fit cursor-pointer select-none"
                                      title="点击切换为可用"
                                    >
                                      <span className="w-1.5 h-1.5 bg-rose-500 rounded-full flex-shrink-0"></span>
                                      占用
                                    </span>
                                  ) : (
                                    <span
                                      onClick={() => handleToggleAccountAvailableStatus(acc.id)}
                                      className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-green-50 hover:bg-green-100 active:scale-[0.97] transition-all text-green-700 border border-green-100 flex items-center gap-1 w-fit cursor-pointer select-none"
                                      title="点击切换为占用"
                                    >
                                      <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                                      可用
                                    </span>
                                  )}
                                </td>
                                <td className="py-2.5 px-2 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                                  {(() => {
                                    const availableHosts = Array.from(new Set(
                                      backendAccounts
                                        .map(a => a.config?.proxy?.host)
                                        .filter(Boolean)
                                    )).filter(h => h !== '127.0.0.1');

                                    const currentHost = acc.config?.proxy?.enabled && acc.config?.proxy?.host 
                                      ? acc.config.proxy.host 
                                      : 'none';

                                    return (
                                      <select
                                        value={currentHost}
                                        onChange={async (e) => {
                                          await handleUpdateAccountProxy(acc.id, e.target.value);
                                        }}
                                        disabled={isAccountLockedForManualOperation(acc)}
                                        title={getAccountTaskStateLabel(acc) || '选择并分配代理'}
                                        className="bg-slate-50 hover:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400 border border-slate-200 text-slate-700 text-[10.5px] py-0.5 px-1.5 rounded focus:outline-none focus:ring-1 focus:ring-blue-500/30 cursor-pointer disabled:cursor-not-allowed font-mono w-full max-w-[125px] transition-all"
                                      >
                                        <option value="none">无代理 / 禁用</option>
                                        {availableHosts.map((host) => {
                                          const isUsedByOthers = backendAccounts.some(
                                            (other) => other.id !== acc.id && 
                                                       other.config?.proxy?.enabled && 
                                                       other.config?.proxy?.host === host
                                          );
                                          return (
                                            <option key={host} value={host}>
                                              {host} {isUsedByOthers ? '(已分配)' : ''}
                                            </option>
                                          );
                                        })}
                                      </select>
                                    );
                                  })()}
                                </td>
                                <td className="py-2.5 px-2 whitespace-nowrap">
                                  {acc.config?.profile_modified ? (
                                    <span
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        if (isAccountLockedForManualOperation(acc)) return;
                                        handleToggleProfileModified(acc.id);
                                      }}
                                      className={`px-2 py-0.5 rounded text-[10px] font-semibold border flex items-center gap-1 w-fit select-none transition-all ${isAccountLockedForManualOperation(acc) ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed' : 'bg-teal-50 hover:bg-teal-100 active:scale-[0.97] text-teal-700 border-teal-100 cursor-pointer'}`}
                                      title={getAccountTaskStateLabel(acc) || (acc.config.profile_modified_name ? `${acc.config.profile_modified_name} (${acc.config.profile_modified_username}) - 点击切换为未修改` : '点击切换为未修改')}
                                    >
                                      <span className="w-1.5 h-1.5 bg-teal-500 rounded-full"></span>
                                      已修改
                                    </span>
                                  ) : (
                                    <span
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        if (isAccountLockedForManualOperation(acc)) return;
                                        handleToggleProfileModified(acc.id);
                                      }}
                                      className={`px-2 py-0.5 rounded text-[10px] font-semibold border inline-block select-none transition-all ${isAccountLockedForManualOperation(acc) ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed' : 'bg-slate-100 hover:bg-slate-200 active:scale-[0.97] text-slate-450 border-slate-200 cursor-pointer'}`}
                                      title={getAccountTaskStateLabel(acc) || '点击切换为已修改'}
                                    >
                                      未修改
                                    </span>
                                  )}
                                </td>
                                <td className="py-2.5 px-2 whitespace-nowrap">
                                  {(() => {
                                    const score = calculateHealthScore(acc);
                                    let colorClass = "bg-rose-50 text-rose-700 border-rose-100";
                                    let label = "受限";
                                    if (score === 100) {
                                      colorClass = "bg-emerald-50 text-emerald-700 border-emerald-100";
                                      label = "正常";
                                    } else if (score === 50) {
                                      colorClass = "bg-amber-50 text-amber-700 border-amber-100";
                                      label = "受限";
                                    } else {
                                      if (acc.is_deactivated) {
                                        colorClass = "bg-rose-50 text-rose-700 border-rose-100";
                                        label = "已注销";
                                      } else {
                                        colorClass = "bg-slate-100 text-slate-400 border-slate-200";
                                        label = "未登录";
                                      }
                                    }
                                    return (
                                      <span
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          setHealthDetailsAccount(acc);
                                          setShowHealthDetailsModal(true);
                                        }}
                                        className={`px-2 py-0.5 rounded text-[10px] font-bold border ${colorClass} cursor-pointer hover:opacity-80 active:scale-[0.97] transition-all`}
                                        title="点击查看健康评分详情及防封建议"
                                      >
                                        {label} ({score}分)
                                      </span>
                                    );
                                  })()}
                                </td>
                                <td className="py-2.5 px-2 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                                  <div className="account-actions flex gap-1 justify-end items-center flex-nowrap">
                                    {acc.isAuthorized && shouldShowAccountUnlockButton(acc) && (
                                      <button
                                        onClick={async () => {
                                          if (!confirm(`确认强制清除账号 +${acc.id} 的当前操作锁？仅建议在账号操作卡死、一直提示 409 正在执行其他操作时使用。`)) return;
                                          try {
                                            const res = await fetch(`${BASE_URL}/api/accounts/${acc.id}/reset-lock`, { method: 'POST' });
                                            if (res.ok) {
                                              alert("重置锁成功！");
                                              fetchBackendAccounts();
                                            } else {
                                              const data = await res.json();
                                              alert(`重置失败: ${data.detail || '未知原因'}`);
                                            }
                                          } catch (err: any) {
                                            alert(`重置出错: ${err.message}`);
                                          }
                                        }}
                                        className="account-action-button px-2 py-1 bg-amber-50 hover:bg-amber-100 text-amber-700 text-[11px] font-semibold rounded-md border border-amber-100 transition-colors"
                                        title={`当前锁定操作：${acc.active_operation_label || acc.active_operation || '未知操作'}。仅账号操作卡死时使用。`}
                                      >
                                        解锁
                                      </button>
                                    )}
                                    {acc.isAuthorized && !isAccountLockedForManualOperation(acc) && (
                                      <>
                                        <button
                                          onClick={() => handleSyncAccountProfile(acc.id)}
                                          disabled={acc.isLoadingStatus}
                                          className="account-action-button px-2 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-[11px] font-semibold rounded-md border border-emerald-100 transition-colors flex items-center gap-1 disabled:opacity-50"
                                          title="同步电报个人信息与用户名"
                                        >
                                          <RefreshCw className={`w-3 h-3 ${acc.isLoadingStatus ? 'animate-spin' : ''}`} />
                                          <span>同步</span>
                                        </button>
                                        <button
                                          onClick={() => handleOpenManageModal(acc)}
                                          className="account-action-button px-2 py-1 bg-slate-50 hover:bg-slate-100 text-slate-600 text-[11px] font-semibold rounded-md border border-slate-100 transition-colors"
                                        >
                                          管理
                                        </button>
                                        <button
                                          onClick={() => handleConfigureBotDirectly(acc)}
                                          disabled={(acc.bot_setup_status || acc.config?.bot_setup_status) === 'approved' || loadingBotAccounts[acc.id]}
                                          className={`account-action-button px-2 py-1 text-[11px] font-semibold rounded-md border transition-colors ${
                                            (acc.bot_setup_status || acc.config?.bot_setup_status) === 'approved'
                                              ? 'bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed'
                                              : 'bg-blue-50 border-blue-100 text-blue-700 hover:bg-blue-100'
                                          }`}
                                        >
                                          {loadingBotAccounts[acc.id] ? '配置中...' : 'BOT'}
                                        </button>
                                      </>
                                    )}
                                    {acc.isAuthorized && isAccountLockedForManualOperation(acc) && (
                                      <span
                                        className="px-2 py-1 bg-slate-100 text-slate-400 text-[11px] font-semibold rounded-md border border-slate-200"
                                        title={getAccountTaskStateLabel(acc)}
                                      >
                                        已锁定
                                      </span>
                                    )}
                                    <button
                                      onClick={() => handleOpenLoginInfoModal(acc)}
                                      className="account-action-button px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 text-[11px] font-semibold rounded-md border border-blue-100 transition-colors"
                                    >
                                      登录
                                    </button>
                                    {userRole === 'admin' && !isAccountLockedForManualOperation(acc) && (
                                      <button
                                        onClick={() => handleDeleteBackendAccount(acc.id)}
                                        className="account-delete-button w-7 h-7 flex items-center justify-center bg-rose-50 hover:bg-rose-100 text-rose-600 hover:text-rose-750 rounded-md border border-rose-100 transition-colors"
                                        title="彻底删除"
                                      >
                                        <X className="w-4 h-4" />
                                      </button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>

                      </div>

                    );

                  })()}

                </>

              )}

              {/* Floating Batch Action Bar for Accounts */}

              {isBatchManagingAccounts && selectedAccountIds.length > 0 && (

                <div className="m-6 p-4 bg-slate-900 text-white rounded-xl flex items-center justify-between shadow-lg animate-fade-in transition-all">

                  <div className="flex items-center gap-3">

                    <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span>

                    <span className="text-xs font-semibold">已选中 {selectedAccountIds.length} 个账号</span>

                  </div>

                  <div className="flex gap-2">

                    <button 

                      onClick={(e) => {

                        e.stopPropagation();

                        setBatchEditTargetIds(selectedAccountIds);

                        setShowBatchProfileModal(true);

                      }}

                      className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold rounded-lg transition-all active:scale-[0.98]"

                    >

                      批量修改个人信息

                    </button>

                    <button 

                      onClick={(e) => {

                        e.stopPropagation();

                        setBatchEditTargetIds(selectedAccountIds);

                        setShowBatch2faModal(true);

                      }}

                      className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg transition-all active:scale-[0.98]"

                    >

                      批量修改两步验证

                    </button>

                    <button 

                      onClick={(e) => {

                        e.stopPropagation();

                        setBatchEditTargetIds(selectedAccountIds);

                        setShowBatchAvatarModal(true);

                      }}

                      className="px-3 py-1.5 bg-pink-600 hover:bg-pink-700 text-white text-xs font-bold rounded-lg transition-all active:scale-[0.98]"

                    >

                      批量修改头像

                    </button>

                    <button 

                      onClick={async (e) => {

                        e.stopPropagation();

                        await handleBatchCheckAccountsStatus();

                      }}

                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-all active:scale-[0.98]"

                    >

                      批量检测状态

                    </button>

                    <button 

                      onClick={async (e) => {

                        e.stopPropagation();

                        await handleBatchClearAccountsSession();

                      }}

                      className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-lg transition-all active:scale-[0.98]"

                    >

                      批量退出登录

                    </button>

                    <button 

                      onClick={async (e) => {

                        e.stopPropagation();

                        await handleBatchTriggerBotSetup();

                      }}

                      disabled={isBotSetupLoading}

                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-bold rounded-lg transition-all active:scale-[0.98]"

                    >

                      一键配置Bot

                    </button>

                    {userRole === 'admin' && (

                      <button 

                        onClick={async (e) => {

                          e.stopPropagation();

                          await handleBatchDeleteAccounts();

                        }}

                        className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-lg transition-all active:scale-[0.98]"

                      >

                        批量彻底删除

                      </button>

                    )}

                  </div>

                </div>

              )}

            </div>

          )}



          {/* TAB 2: GROUPS MAINTENANCE */}

          {activeTab === 'groups' && (

            <div className="bg-white border border-slate-100 rounded-2xl shadow-sm flex flex-col">

              <div className="p-6 border-b border-slate-50 bg-slate-50/20 flex justify-between items-center">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">群组库维护</h3>

                  <p className="text-xs text-slate-400 mt-0.5 font-light">通过本地 JSON 文件与电报 API 维护群组数据</p>

                </div>

                <div className="flex gap-2">

                  {isBatchManaging ? (

                    <button 

                      onClick={() => {

                        setIsBatchManaging(false);

                        setSelectedGroupIds([]);

                      }}

                      className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg text-xs font-bold shadow-sm transition-all"

                    >

                      退出管理

                    </button>

                  ) : (

                    <>

                      <button 

                        onClick={() => {

                          setIsBatchManaging(true);

                          setSelectedGroupIds([]);

                        }}

                        className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-bold shadow-sm transition-all"

                      >

                        ⚙️ 批量管理

                      </button>

                      <button 

                        onClick={() => setShowAddGroupModal(true)}

                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-sm transition-all flex items-center gap-1.5 active:scale-[0.98]"

                      >

                        <PlusCircle className="w-4 h-4" />

                        <span>添加群组</span>

                      </button>

                      <button

                        onClick={() => {

                          fetchGroupCategories();

                          setShowManageCategoriesModal(true);

                        }}

                        className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-bold shadow-sm transition-all flex items-center gap-1.5 active:scale-[0.98]"

                      >

                        <span>📁</span>

                        <span>管理群组类型</span>

                      </button>

                    </>

                  )}

                  <button 

                    onClick={handleRunGroupSyncWithLogs}

                    disabled={groupSyncRunning}

                    className="px-4 py-2 bg-slate-100 hover:bg-slate-200 disabled:opacity-60 disabled:cursor-not-allowed text-slate-700 border border-slate-200 rounded-lg text-xs font-bold shadow-sm transition-all active:scale-[0.98]"

                  >

                    {groupSyncRunning ? '🔄 正在同步...' : '🔄 同步群组状态'}

                  </button>

                </div>

              </div>



              <div className="px-6 pt-4 flex items-center justify-between gap-3 flex-wrap">

                <div className="text-[11px] text-slate-400">

                  当前 {groups.length} 个群组，评分为同步时生成的基础活跃评分

                </div>

                <div className="flex items-center gap-2">

                  <span className="text-[11px] text-slate-400 font-semibold">排序：</span>

                  <select

                    value={groupSortField}

                    onChange={(e) => setGroupSortField(e.target.value as typeof groupSortField)}

                    className="h-8 px-2 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/10"

                  >

                    <option value="default">默认顺序</option>

                    <option value="quality">质量评分</option>

                    <option value="members">群人数</option>

                    <option value="status">启用状态</option>

                    <option value="title">群组标题</option>

                  </select>

                  <button

                    type="button"

                    onClick={() => setGroupSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}

                    disabled={groupSortField === 'default'}

                    className="h-8 px-3 bg-slate-100 hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-200 rounded-lg text-xs font-bold text-slate-600 transition-colors"

                  >

                    {groupSortOrder === 'desc' ? '从高到低' : '从低到高'}

                  </button>

                </div>

              </div>



              {/* Batch controls stay above the group table so selected actions are always visible. */}

              {isBatchManaging && selectedGroupIds.length > 0 && (

                <div className="mx-6 mt-4 mb-0 p-3 bg-slate-900 text-white rounded-xl flex items-center justify-between gap-3 shadow-lg animate-fade-in transition-all">

                  <div className="flex items-center gap-3 shrink-0">

                    <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span>

                    <span className="text-xs font-semibold whitespace-nowrap">已选中 {selectedGroupIds.length} 个群组</span>

                  </div>

                  <div className="flex flex-wrap justify-end gap-2">

                    <button 

                      onClick={async (e) => {

                        e.stopPropagation();

                        await handleBatchUpdateCategory('中文广告');

                      }}

                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-all whitespace-nowrap"

                    >

                      设为中文广告

                    </button>

                    <button 

                      onClick={async (e) => {

                        e.stopPropagation();

                        await handleBatchUpdateCategory('英文广告');

                      }}

                      className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold rounded-lg transition-all whitespace-nowrap"

                    >

                      设为英文广告

                    </button>

                    <button 

                      onClick={async (e) => {

                        e.stopPropagation();

                        await handleBatchDeleteGroups();

                      }}

                      className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-lg transition-all whitespace-nowrap"

                    >

                      批量删除

                    </button>

                  </div>

                </div>

              )}

              {/* Group table list */}

              <div className="overflow-x-auto">

                <table className="w-full min-w-[1120px] text-left border-collapse table-fixed">

                  <thead>

                    <tr className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-semibold uppercase text-slate-400 tracking-wider">

                      {isBatchManaging && (

                        <th className="py-3 px-3 w-10 text-center">

                          <input 

                            type="checkbox" 

                            checked={groups.length > 0 && selectedGroupIds.length === groups.length}

                            onChange={handleToggleSelectAllGroups}

                            className="rounded text-blue-600 focus:ring-blue-500/20 border-slate-300 cursor-pointer"

                          />

                        </th>

                      )}

                      <th className="py-3 px-3 w-[12%]">群组 ID</th>

                      <th className="py-3 px-3 w-[28%]">群组标题</th>

                      <th className="py-3 px-3 w-[18%]">用户名</th>

                      <th className="py-3 px-3 w-[13%]">群组类型</th>

                      <th className="py-3 px-3 w-[8%]">群人数</th>

                      <th className="py-3 px-3 w-[7%]">评分</th>

                      <th className="py-3 px-3 w-[8%]">状态</th>

                      <th className="py-3 px-3 w-[6%] text-right">操作</th>

                    </tr>

                  </thead>

                  <tbody>

                    {groups.length === 0 ? (

                      <tr>

                        <td colSpan={isBatchManaging ? 9 : 8} className="py-8 text-center text-slate-400 text-xs font-light">

                          暂无群组数据，点击上方“添加群组”按钮校验并加入。

                        </td>

                      </tr>

                    ) : (

                      sortedGroups.map((group) => (

                        <tr 

                          key={group.id} 

                          onClick={() => {

                            if (isBatchManaging) {

                              handleToggleSelectGroup(group.id);

                            }

                          }}

                          className={`border-b border-slate-50 text-sm text-slate-700 hover:bg-slate-50/40 transition-colors ${

                            isBatchManaging ? 'cursor-pointer select-none bg-slate-50/10' : ''

                          } ${

                            isBatchManaging && selectedGroupIds.includes(group.id) ? '!bg-blue-50/30' : ''

                          }`}

                        >

                          {isBatchManaging && (

                            <td className="py-3 px-3 w-10 text-center" onClick={(e) => e.stopPropagation()}>

                              <input 

                                type="checkbox" 

                                checked={selectedGroupIds.includes(group.id)}

                                onChange={() => handleToggleSelectGroup(group.id)}

                                className="rounded text-blue-600 focus:ring-blue-500/20 border-slate-300 cursor-pointer"

                              />

                            </td>

                          )}

                          <td className="py-3 px-3 font-mono text-xs text-slate-500 whitespace-nowrap">{group.id}</td>

                          <td className="py-3 px-3 break-words">

                            <div 

                              className="text-slate-900 font-semibold line-clamp-2 leading-snug text-[13px]" 

                              style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}

                              title={group.title}

                            >

                              {group.title}

                            </div>

                          </td>

                          <td className="py-3 px-3 font-mono text-xs text-blue-500 truncate">

                            {group.username ? (

                              <button

                                type="button"

                                onClick={(e) => {

                                  e.stopPropagation();

                                  setGroupJoinTarget(group);

                                }}

                                className="inline-flex items-center gap-1 max-w-full text-blue-600 hover:text-blue-700 hover:underline font-semibold align-middle"

                                title={`打开 @${group.username.replace(/^@+/, '')}`}

                              >

                                <span className="truncate">@{group.username.replace(/^@+/, '')}</span>

                                <ExternalLink className="w-3 h-3 shrink-0" />

                              </button>

                            ) : <span className="text-slate-300">无</span>}

                          </td>

                          <td className="py-3 px-3 whitespace-nowrap">

                            <select

                              value={group.category || ''}

                              onChange={(e) => handleUpdateGroupCategory(group.id, e.target.value)}

                              onClick={(e) => e.stopPropagation()}

                              className={`px-2 py-0.5 border rounded text-[10px] font-semibold cursor-pointer outline-none ${

                                group.type === 'channel'

                                  ? 'text-purple-600 border-purple-200 bg-purple-50/50 focus:border-purple-400'

                                  : 'text-blue-600 border-blue-200 bg-blue-50/50 focus:border-blue-400'

                              }`}

                            >

                              {(groupCategories.length > 0 ? groupCategories.map(c => c.name) : ['中文长', '中文短', '英文长', '英文短']).map(catName => (

                                <option key={catName} value={catName} className="text-slate-800 bg-white">

                                  {catName}

                                </option>

                              ))}

                            </select>

                          </td>

                          <td className="py-3 px-3 font-mono text-xs whitespace-nowrap">{(group.memberCount || 0).toLocaleString()}</td>

                          <td className="py-3 px-3 whitespace-nowrap">

                            <span

                              className={`px-2 py-0.5 rounded text-[10px] font-black border font-mono inline-block ${getGroupScoreBadgeClass(getGroupQualityScore(group))}`}

                              title={`质量评分 ${getGroupQualityScore(group)} / 100`}

                            >

                              {getGroupQualityScore(group)}

                            </span>

                          </td>

                          <td className="py-3 px-3 whitespace-nowrap">

                            <button 

                              onClick={(e) => {

                                e.stopPropagation();

                                handleToggleGroup(group.id, !group.enabled);

                              }}

                              className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap inline-block ${

                                group.enabled 

                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' 

                                  : 'bg-slate-100 text-slate-400'

                              }`}

                            >

                              {group.enabled ? '已启用' : '已禁用'}

                            </button>

                          </td>

                          <td className="py-3 px-3 text-right">

                            <button 

                              onClick={(e) => {

                                e.stopPropagation();

                                handleDeleteGroup(group.id);

                              }}

                              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors inline-flex"

                              title="删除群组"

                            >

                              <Trash2 className="w-4 h-4" />

                            </button>

                          </td>

                        </tr>

                      ))

                    )}

                  </tbody>

                </table>

              </div>


            </div>

          )}



                    {/* TAB 3: AUTO JOIN */}

          {activeTab === 'join' && (

            <div className="bg-slate-50/40 rounded-2xl flex flex-col gap-6 p-1">

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 items-start">

                

                {/* Left Column: Task Configuration */}

                <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm flex flex-col gap-6">

                  <div>

                    <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">

                      ⚙️ 入群任务配置

                    </h3>

                    <p className="text-xs text-slate-400 mt-0.5">配置执行账号、目标链接以及防风控安全策略</p>

                  </div>



                  {/* 1. Account Selector list */}

                  <div className="flex flex-col gap-2">

                    <div className="flex justify-between items-center">

                      <label className="text-sm font-semibold text-slate-700">1. 选择执行账号</label>

                      <button

                        type="button"

                        disabled={joinRunning}

                        onClick={() => {

                          const authorizedAccountIds = backendAccounts.filter(isAccountSelectableForTask).map(acc => acc.id);

                          if (selectedJoinAccounts.length === authorizedAccountIds.length) {

                            setSelectedJoinAccounts([]);

                          } else {

                            setSelectedJoinAccounts(authorizedAccountIds);

                          }

                        }}

                        className="text-xs text-blue-600 hover:text-blue-700 font-semibold disabled:opacity-50 disabled:cursor-not-allowed"

                      >

                        {selectedJoinAccounts.length === backendAccounts.filter(isAccountSelectableForTask).length ? "取消全选" : "全选可执行账号"}

                      </button>

                    </div>



                    <div className="border border-slate-100 rounded-xl p-3 max-h-40 overflow-y-auto flex flex-col gap-2 bg-slate-50/20">

                      {backendAccounts.filter(isAccountSelectableForTask).length === 0 ? (

                        <span className="text-xs text-slate-400 text-center py-4">暂无可执行账号，请先确认账号已登录且状态为可用。</span>

                      ) : (

                        backendAccounts.filter(isAccountSelectableForTask).map(acc => {

                          const isChecked = selectedJoinAccounts.includes(acc.id);
                          const isSelectable = isAccountSelectableForTask(acc);
                          const disabledReason = getAccountTaskStateLabel(acc);

                          return (

                            <label key={acc.id} className={`flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 rounded-lg transition-colors ${!isSelectable ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>

                              <input

                                type="checkbox"

                                checked={isChecked}

                                disabled={joinRunning || !isSelectable}

                                onChange={() => {
                                  if (!isSelectable) return;

                                  if (isChecked) {

                                    setSelectedJoinAccounts(prev => prev.filter(id => id !== acc.id));

                                  } else {

                                    setSelectedJoinAccounts(prev => [...prev, acc.id]);

                                  }

                                }}

                                className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-4 h-4 disabled:opacity-50 disabled:cursor-not-allowed"

                              />

                              <span className="text-xs font-mono font-bold text-slate-700">{acc.name}</span>

                              {acc.meInfo && (

                                <span className="text-[10px] text-slate-400">({acc.meInfo})</span>

                              )}

                               {!isSelectable && disabledReason && (
                                 <span className="text-red-500 font-semibold ml-auto text-[10px] flex items-center gap-1">
                                   ❗ {disabledReason}
                                </span>
                              )}
                            </label>

                          );

                        })

                      )}

                    </div>

                  </div>



                  {/* 2. Join Links Textarea */}

                  <div className="flex flex-col gap-2">

                    <label className="text-sm font-semibold text-slate-700">2. 输入加群链接列表 (每行一个)</label>

                    <textarea

                      value={joinLinks}

                      onChange={(e) => setJoinLinks(e.target.value)}

                      disabled={joinRunning}

                      placeholder="支持公共群组链接 (如 https://t.me/RosePayChatGroup) 或私有邀请链接 (如 https://t.me/+ABCDE...)"

                      className="w-full h-32 bg-slate-50/60 border border-slate-200 rounded-xl p-3.5 font-mono text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 resize-none transition-all disabled:opacity-75 disabled:cursor-not-allowed"

                    ></textarea>



                    {/* Quick select groups from library */}

                    <div className="flex flex-col gap-2 mt-1 border border-slate-100 rounded-xl p-3 bg-slate-50/20">

                      <div className="flex justify-between items-center pb-1 border-b border-slate-100">

                        <span className="text-xs font-semibold text-slate-600 flex items-center gap-1">

                          📁 从系统群组库快捷选择 <span className="text-[10px] text-slate-400 font-normal font-sans">(勾选直接添加/取消)</span>

                        </span>

                        {groups.length > 0 && (

                          <button

                            type="button"

                            disabled={joinRunning}

                            onClick={() => {

                              const allInLinks = groups.every(g => {

                                const username = g.username ? g.username.replace('@', '').toLowerCase() : '';

                                const id = g.id.toString().toLowerCase();

                                const currentLines = joinLinks.split('\n').map(l => l.trim().toLowerCase());

                                return currentLines.some(line => {

                                  if (line === id) return true;

                                  if (username) {

                                    if (line === `@${username}` || line === username) return true;

                                    if (line.includes(`t.me/${username}`)) return true;

                                  }

                                  return false;

                                });

                              });



                              if (allInLinks) {

                                // Remove all of them

                                const groupIds = groups.map(g => g.id.toString().toLowerCase());

                                const usernames = groups.map(g => g.username ? g.username.replace('@', '').toLowerCase() : '').filter(Boolean);

                                const currentLines = joinLinks.split('\n').map(l => l.trim()).filter(l => l !== '');

                                const filtered = currentLines.filter(line => {

                                  const norm = line.toLowerCase();

                                  if (groupIds.includes(norm)) return false;

                                  const usernameMatch = usernames.some(u => norm === `@${u}` || norm === u || norm.includes(`t.me/${u}`));

                                  if (usernameMatch) return false;

                                  return true;

                                });

                                setJoinLinks(filtered.join('\n'));

                              } else {

                                // Add all missing

                                const currentLines = joinLinks.split('\n').map(l => l.trim()).filter(l => l !== '');

                                const toAdd: string[] = [];

                                groups.forEach(g => {

                                  const username = g.username ? g.username.replace('@', '').toLowerCase() : '';

                                  const id = g.id.toString().toLowerCase();

                                  const isPresent = currentLines.some(line => {

                                    const norm = line.toLowerCase();

                                    if (norm === id) return true;

                                    if (username) {

                                      if (norm === `@${username}` || norm === username) return true;

                                      if (norm.includes(`t.me/${username}`)) return true;

                                    }

                                    return false;

                                  });

                                  if (!isPresent) {

                                    toAdd.push(g.username ? (g.username.startsWith('@') ? g.username : `@${g.username}`) : g.id);

                                  }

                                });

                                setJoinLinks([...currentLines, ...toAdd].join('\n'));

                              }

                            }}

                            className="text-[10px] text-blue-600 hover:text-blue-700 font-semibold disabled:opacity-50 disabled:cursor-not-allowed"

                          >

                            {(() => {

                              const allInLinks = groups.every(g => {

                                const username = g.username ? g.username.replace('@', '').toLowerCase() : '';

                                const id = g.id.toString().toLowerCase();

                                const currentLines = joinLinks.split('\n').map(l => l.trim().toLowerCase());

                                return currentLines.some(line => {

                                  if (line === id) return true;

                                  if (username) {

                                    if (line === `@${username}` || line === username) return true;

                                    if (line.includes(`t.me/${username}`)) return true;

                                  }

                                  return false;

                                });

                              });

                              return allInLinks ? "取消全选" : "全选所有";

                            })()}

                          </button>

                        )}

                      </div>



                      <div className="max-h-48 overflow-y-auto flex flex-col gap-1.5 border border-slate-100 rounded-lg p-2 bg-white mt-1">

                        {groups.length === 0 ? (

                          <div className="text-[10px] text-slate-400 text-center py-6">群组库暂无数据，请先到“群组维护”页面同步或添加群组。</div>

                        ) : (

                          groups.map(g => {

                            const username = g.username ? g.username.replace('@', '').toLowerCase() : '';

                            const id = g.id.toString().toLowerCase();

                            const currentLines = joinLinks.split('\n').map(l => l.trim().toLowerCase());

                            const isChecked = currentLines.some(line => {

                              if (line === id) return true;

                              if (username) {

                                if (line === `@${username}` || line === username) return true;

                                if (line.includes(`t.me/${username}`)) return true;

                              }

                              return false;

                            });



                            return (

                              <label key={g.id} className="flex items-center justify-between px-2 py-1.5 hover:bg-slate-50 rounded cursor-pointer transition-colors text-[11px] text-slate-700">

                                <div className="flex items-center gap-2 overflow-hidden mr-2">

                                  <input

                                    type="checkbox"

                                    checked={isChecked}

                                    disabled={joinRunning}

                                    onChange={() => {

                                      const currentLines = joinLinks.split('\n').map(l => l.trim()).filter(l => l !== '');

                                      if (isChecked) {

                                        // Remove it

                                        const filtered = currentLines.filter(line => {

                                          const norm = line.toLowerCase();

                                          if (norm === id) return false;

                                          if (username) {

                                            if (norm === `@${username}` || norm === username) return false;

                                            if (norm.includes(`t.me/${username}`)) return false;

                                          }

                                          return true;

                                        });

                                        setJoinLinks(filtered.join('\n'));

                                      } else {

                                        // Append it

                                        const targetLink = g.username 

                                          ? (g.username.startsWith('@') ? g.username : `@${g.username}`) 

                                          : g.id;

                                        setJoinLinks([...currentLines, targetLink].join('\n'));

                                      }

                                    }}

                                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-3.5 h-3.5 flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"

                                  />

                                  <span className="font-semibold truncate max-w-[140px] text-slate-800">{g.title || '未命名群组'}</span>

                                  <span className="text-slate-400 font-mono text-[9px] truncate">({g.username ? `@${g.username}` : g.id})</span>

                                </div>

                                <span className="text-[9px] text-slate-400 font-mono flex-shrink-0">{g.memberCount ? `${g.memberCount}人` : ''}</span>

                              </label>

                            );

                          })

                        )}

                      </div>

                    </div>

                  </div>



                  {/* 3. Execution Mode */}

                  <div className="flex flex-col gap-2">

                    <label className="text-sm font-semibold text-slate-700">3. 多账号执行模式</label>

                    <div className="flex gap-6 mt-1">

                      <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">

                        <input

                          type="radio"

                          name="joinMode"

                          disabled={joinRunning}

                          checked={joinMode === 'sequential'}

                          onChange={() => setJoinMode('sequential')}

                          className="text-blue-600 focus:ring-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed"

                        />

                        <span>单账号队列执行 (轮流加入，更安全)</span>

                      </label>

                      <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">

                        <input

                          type="radio"

                          name="joinMode"

                          disabled={joinRunning}

                          checked={joinMode === 'simultaneous'}

                          onChange={() => setJoinMode('simultaneous')}

                          className="text-blue-600 focus:ring-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed"

                        />

                        <span>多账号并发进行 (效率高)</span>

                      </label>

                    </div>

                  </div>



                  {/* 4. Interval Strategy */}

                  <div className="flex flex-col gap-2">

                    <label className="text-sm font-semibold text-slate-700">4. 加群时间间隔与防封策略</label>

                    

                    <div className="flex gap-6 mt-1 mb-2">

                      <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">

                        <input

                          type="radio"

                          name="joinStrategy"

                          disabled={joinRunning}

                          checked={joinStrategy === 'fixed'}

                          onChange={() => setJoinStrategy('fixed')}

                          className="text-blue-600 focus:ring-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed"

                        />

                        <span>按固定时间间隔 (必须 &ge; 30秒)</span>

                      </label>

                      <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">

                        <input

                          type="radio"

                          name="joinStrategy"

                          disabled={joinRunning}

                          checked={joinStrategy === 'safety'}

                          onChange={() => setJoinStrategy('safety')}

                          className="text-blue-600 focus:ring-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed"

                        />

                        <span>安全防风控频率模式</span>

                      </label>

                    </div>



                    {joinStrategy === 'fixed' ? (

                      <div className="flex items-center gap-3 bg-slate-50/50 border border-slate-100 rounded-xl p-3">

                        <span className="text-xs text-slate-500">固定加群间隔:</span>

                        <input

                          type="number"

                          value={joinDelay}

                          disabled={joinRunning}

                          onChange={(e) => { const val = e.target.value; setJoinDelay(val === '' ? '' : parseInt(val) || 0); }}

                          min={30}

                          className="w-20 bg-white border border-slate-200 rounded-lg p-1 text-xs text-center font-mono font-bold text-slate-700 disabled:opacity-60 disabled:cursor-not-allowed"

                        />

                        <span className="text-xs text-slate-400">秒 (系统限制最少 30 秒)</span>

                      </div>

                    ) : (

                      <div className="flex items-center gap-2 flex-wrap bg-slate-50/50 border border-slate-100 rounded-xl p-3">

                        <span className="text-xs text-slate-500">在</span>

                        <input

                          type="number"

                          value={joinSafetyMinutes}

                          disabled={joinRunning}

                          onChange={(e) => { const val = e.target.value; setJoinSafetyMinutes(val === '' ? '' : parseInt(val) || 0); }}

                          className="w-14 bg-white border border-slate-200 rounded-lg p-1 text-xs text-center font-mono font-bold text-slate-700 disabled:opacity-60 disabled:cursor-not-allowed"

                        />

                        <span className="text-xs text-slate-500">分钟内，每个账号最多加入</span>

                        <input

                          type="number"

                          value={joinSafetyGroups}

                          disabled={joinRunning}

                          onChange={(e) => { const val = e.target.value; setJoinSafetyGroups(val === '' ? '' : parseInt(val) || 0); }}

                          className="w-14 bg-white border border-slate-200 rounded-lg p-1 text-xs text-center font-mono font-bold text-slate-700 disabled:opacity-60 disabled:cursor-not-allowed"

                        />

                        <span className="text-xs text-slate-500">个群组</span>

                        

                        <div className="w-full mt-2 pt-2 border-t border-slate-200/40 text-[10px] text-slate-400 leading-relaxed">

                          提示：当前安全设置平均加群间隔为: <span className="font-bold text-blue-600 font-mono">{(joinSafetyMinutes && joinSafetyGroups) ? ((Number(joinSafetyMinutes) * 60) / Number(joinSafetyGroups)).toFixed(1) : '0.0'} 秒</span>。

                          电报限制单日加入上限约 15-20 个，平均间隔必须大等于 30 秒。

                        </div>

                      </div>

                    )}

                  </div>



                  {/* 5. Automatic Folder Sync Option */}
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-semibold text-slate-700">5. 自动加入聊天文件夹</label>
                    <div className="flex flex-col gap-3 mt-1 bg-slate-50/50 border border-slate-100 rounded-xl p-3">
                      <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          disabled={joinRunning}
                          checked={moveJoinToFolder}
                          onChange={(e) => setMoveJoinToFolder(e.target.checked)}
                          className="rounded text-blue-600 focus:ring-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                        />
                        <span>入群成功后，自动将群组加入聊天文件夹</span>
                      </label>
                      {moveJoinToFolder && (
                        <div className="flex flex-col gap-2 animate-in fade-in slide-in-from-top-1 duration-200 pl-1">
                          <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none">
                            <input
                              type="radio"
                              name="joinFolderMode"
                              disabled={joinRunning}
                              checked={joinFolderByType}
                              onChange={() => setJoinFolderByType(true)}
                              className="text-blue-600 focus:ring-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                            />
                            <span>按群组类型自动分类（创建“中文长/短”、“英文长/短”）</span>
                          </label>
                          <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none">
                            <input
                              type="radio"
                              name="joinFolderMode"
                              disabled={joinRunning}
                              checked={!joinFolderByType}
                              onChange={() => setJoinFolderByType(false)}
                              className="text-blue-600 focus:ring-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                            />
                            <span>手动指定文件夹名称</span>
                          </label>
                          {!joinFolderByType && (
                            <div className="flex items-center gap-2 pt-1">
                              <span className="text-xs text-slate-500 whitespace-nowrap">文件夹名称:</span>
                              <input
                                type="text"
                                value={joinTargetFolderName}
                                disabled={joinRunning}
                                onChange={(e) => setJoinTargetFolderName(e.target.value)}
                                placeholder="例如：广告"
                                className="flex-1 bg-white border border-slate-200 rounded-lg px-2.5 py-1 text-xs text-slate-700 disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-1 focus:ring-blue-500"
                              />
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 6. Start/Stop Action Buttons */}

                  <div className="flex gap-3 mt-2">

                    {!joinRunning ? (

                      <button

                        onClick={handleStartJoinTask}

                        disabled={selectedJoinAccounts.length === 0}

                        className="flex-grow py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl text-sm font-bold shadow-md shadow-emerald-600/10 transition-all flex items-center justify-center gap-2 active:scale-[0.98]"

                      >

                        <Play className="w-4 h-4" />

                        <span>启动自动入群任务</span>

                      </button>

                    ) : (

                      <button

                        onClick={handleStopJoinTask}

                        className="flex-grow py-3 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-sm font-bold shadow-md shadow-rose-600/10 transition-all flex items-center justify-center gap-2 active:scale-[0.98]"

                      >

                        <Pause className="w-4 h-4 animate-pulse" />

                        <span>手动停止当前任务</span>

                      </button>

                    )}

                  </div>

                </div>



                {/* Right Column: Execution Status & Analysis Statistics Board */}

                <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm flex flex-col gap-6 min-h-[500px]">

                  <div>

                    <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">

                      {joinRunning ? "📊 任务执行监控与发言分析" : selectedHistoryTask ? "📜 历史任务执行详情" : "📋 历史入群任务记录"}

                    </h3>

                    <p className="text-xs text-slate-400 mt-0.5">

                      {joinRunning 

                        ? "监控加群实时进度、异常统计及发言权限筛选" 

                        : selectedHistoryTask 

                          ? "查看该次归档任务的详细参数、日志及加群结果列表" 

                          : "点击任意一条历史记录查看其完整的加群日志与执行详情"}

                    </p>

                  </div>



                  {joinRunning ? (

                    <div className="flex flex-col gap-5 flex-grow">

                      

                      {/* Progress Metrics Bar */}

                      <div className="flex flex-col gap-2">

                        <div className="flex justify-between text-xs font-bold text-slate-600">

                          <span>总执行进度</span>

                          <span className="font-mono">{joinProgress.current} / {joinProgress.total} ({joinProgress.total > 0 ? Math.round((joinProgress.current / joinProgress.total) * 100) : 0}%)</span>

                        </div>

                        <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">

                          <div

                            className="h-full bg-blue-600 transition-all duration-500 rounded-full"

                            style={{ width: `${joinProgress.total > 0 ? (joinProgress.current / joinProgress.total) * 100 : 0}%` }}

                          ></div>

                        </div>

                      </div>



                      {/* Diagnostic Analysis Metrics Grid */}

                      <div className="grid grid-cols-3 gap-3">

                        <div className="bg-emerald-50/50 border border-emerald-100/50 rounded-xl p-3 text-center">

                          <span className="text-[10px] text-slate-400 font-medium block">可以直接发言</span>

                          <span className="text-xl font-bold text-emerald-600 font-mono mt-1 block">

                            {joinResults.filter(r => r.status === 'success').length}

                          </span>

                        </div>

                        <div className="bg-amber-50/50 border border-amber-100/50 rounded-xl p-3 text-center">

                          <span className="text-[10px] text-slate-400 font-medium block">不能发言 (受限/频道)</span>

                          <span className="text-xl font-bold text-amber-600 font-mono mt-1 block">

                            {joinResults.filter(r => r.status === 'restricted').length}

                          </span>

                        </div>

                        <div className="bg-rose-50/50 border border-rose-100/50 rounded-xl p-3 text-center">

                          <span className="text-[10px] text-slate-400 font-medium block">加入失败 (限制)</span>

                          <span className="text-xl font-bold text-rose-600 font-mono mt-1 block">

                            {joinResults.filter(r => r.status === 'failed').length}

                          </span>

                        </div>

                      </div>



                      {/* Live Terminal logs */}

                      <div className="flex flex-col gap-1.5">

                        <span className="text-xs font-semibold text-slate-700">🖥️ 实时执行日志</span>

                        <div ref={joinLogsContainerRef} className="bg-slate-900 rounded-xl p-4 font-mono text-[10px] text-slate-300 h-32 overflow-y-auto flex flex-col gap-1 shadow-inner leading-relaxed">

                          {joinLogs.length === 0 ? (

                            <span className="text-slate-500 italic">等待任务日志输出...</span>

                          ) : (

                            joinLogs.map((log, idx) => (

                              <div key={idx} className="border-l-2 border-slate-700 pl-2">

                                <span className="text-slate-500">[{new Date().toLocaleTimeString()}]</span> {log}

                              </div>

                            ))

                          )}

                        </div>

                      </div>



                      {/* Statistics result list */}

                      <div className="flex flex-col gap-2 flex-grow">

                        <div className="flex justify-between items-center">

                          <span className="text-xs font-semibold text-slate-700">📋 加群结果明细</span>

                          <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer select-none">

                            <input

                              type="checkbox"

                              checked={filterRestricted}

                              onChange={(e) => setFilterRestricted(e.target.checked)}

                              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-3.5 h-3.5"

                            />

                            <span className="font-medium text-amber-600">仅筛选不能直接对话的群组 ({joinResults.filter(r => r.status !== 'success').length})</span>

                          </label>

                        </div>



                        <div className="border border-slate-100 rounded-xl overflow-hidden flex-grow max-h-48 overflow-y-auto bg-slate-50/20">

                          {joinResults.length === 0 ? (

                            <div className="text-center py-8 text-xs text-slate-400">暂无入群结果记录。</div>

                          ) : (

                            <table className="w-full border-collapse text-left">

                              <thead>

                                <tr className="bg-slate-50 text-[10px] text-slate-400 font-bold uppercase tracking-wider border-b border-slate-100">

                                  <th className="px-4 py-2">账号</th>

                                  <th className="px-4 py-2">群组链接</th>

                                  <th className="px-4 py-2">状态</th>

                                </tr>

                              </thead>

                              <tbody className="divide-y divide-slate-50 text-xs">

                                {joinResults

                                  .filter(r => !filterRestricted || r.status !== 'success')

                                  .map((item, idx) => (

                                    <tr key={idx} className="hover:bg-slate-50/60 transition-colors">

                                      <td className="px-4 py-2.5 font-mono text-slate-600">{item.phone}</td>

                                      <td className="px-4 py-2.5 font-mono text-slate-500 truncate max-w-[150px]" title={item.link}>

                                        {item.link}

                                      </td>

                                      <td className="px-4 py-2.5">

                                        {item.status === 'success' && (

                                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">

                                            ✔ 可直接对话

                                          </span>

                                        )}

                                        {item.status === 'restricted' && (

                                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-100" title={item.error}>

                                            ⚠ 不能对话

                                          </span>

                                        )}

                                        {item.status === 'failed' && (

                                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-rose-50 text-rose-700 border border-rose-100" title={item.error}>

                                            ❌ 失败

                                          </span>

                                        )}

                                      </td>

                                    </tr>

                                  ))}

                              </tbody>

                            </table>

                          )}

                        </div>

                      </div>



                    </div>

                  ) : selectedHistoryTask ? (

                    <div className="flex flex-col gap-5 flex-grow">

                      {/* Back button and Meta */}

                      <div className="flex items-center justify-between pb-3 border-b border-slate-100">

                        <button

                          type="button"

                          onClick={() => setSelectedHistoryTask(null)}

                          className="text-xs text-blue-600 hover:text-blue-700 font-semibold flex items-center gap-1 active:scale-[0.98]"

                        >

                          <span>← 返回历史列表</span>

                        </button>

                        <div className="flex items-center gap-2">

                          <span className="text-xs text-slate-400 font-mono">

                            {selectedHistoryTask.created_at ? new Date(selectedHistoryTask.created_at).toLocaleString() : ''}

                          </span>

                          {selectedHistoryTask.status === 'completed' && (

                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100">

                              ✔ 已完成

                            </span>

                          )}

                          {selectedHistoryTask.status === 'stopped' && (

                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-50 text-slate-500 border border-slate-200">

                              ■ 已停止

                            </span>

                          )}

                          {selectedHistoryTask.status === 'failed' && (

                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-100">

                              ❌ 失败

                            </span>

                          )}

                        </div>

                      </div>



                      {/* Progress Metrics Bar */}

                      <div className="flex flex-col gap-2">

                        <div className="flex justify-between text-xs font-bold text-slate-600">

                          <span>任务执行进度</span>

                          <span className="font-mono">

                            {selectedHistoryTask.progress?.current || 0} / {selectedHistoryTask.progress?.total || 0} (

                            {selectedHistoryTask.progress?.total > 0

                              ? Math.round(((selectedHistoryTask.progress?.current || 0) / (selectedHistoryTask.progress?.total || 1)) * 100)

                              : 0}

                            %)

                          </span>

                        </div>

                        <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">

                          <div

                            className="h-full bg-blue-500 transition-all duration-300"

                            style={{

                              width: `${

                                selectedHistoryTask.progress?.total > 0

                                  ? ((selectedHistoryTask.progress?.current || 0) / (selectedHistoryTask.progress?.total || 1)) * 100

                                  : 0

                              }%`,

                            }}

                          ></div>

                        </div>

                      </div>



                      {/* Diagnostic Analysis Metrics Grid */}

                      <div className="grid grid-cols-3 gap-3">

                        <div className="bg-emerald-50/50 border border-emerald-100/50 rounded-xl p-3 text-center">

                          <span className="text-[10px] text-slate-400 font-medium block">可以直接发言</span>

                          <span className="text-xl font-bold text-emerald-600 font-mono mt-1 block">

                            {selectedHistoryTask.results?.filter((r: any) => r.status === 'success').length || 0}

                          </span>

                        </div>

                        <div className="bg-amber-50/50 border border-amber-100/50 rounded-xl p-3 text-center">

                          <span className="text-[10px] text-slate-400 font-medium block">不能发言 (受限/频道)</span>

                          <span className="text-xl font-bold text-amber-600 font-mono mt-1 block">

                            {selectedHistoryTask.results?.filter((r: any) => r.status === 'restricted').length || 0}

                          </span>

                        </div>

                        <div className="bg-rose-50/50 border border-rose-100/50 rounded-xl p-3 text-center">

                          <span className="text-[10px] text-slate-400 font-medium block">加入失败 (限制)</span>

                          <span className="text-xl font-bold text-rose-600 font-mono mt-1 block">

                            {selectedHistoryTask.results?.filter((r: any) => r.status === 'failed' || r.status === 'invalid').length || 0}

                          </span>

                        </div>

                      </div>



                      {/* Live Terminal logs */}

                      <div className="flex flex-col gap-1.5">

                        <span className="text-xs font-semibold text-slate-700">🖥️ 归档执行日志</span>

                        <div className="bg-slate-900 rounded-xl p-4 font-mono text-[10px] text-slate-300 h-32 overflow-y-auto flex flex-col gap-1 shadow-inner leading-relaxed">

                          {!selectedHistoryTask.logs || selectedHistoryTask.logs.length === 0 ? (

                            <span className="text-slate-500 italic">无日志记录</span>

                          ) : (

                            selectedHistoryTask.logs.map((log: string, idx: number) => (

                              <div key={idx} className="border-l-2 border-slate-700 pl-2">

                                <span className="text-slate-500">[{selectedHistoryTask.created_at ? new Date(selectedHistoryTask.created_at).toLocaleTimeString() : 'Log'}]</span> {log}

                              </div>

                            ))

                          )}

                        </div>

                      </div>



                      {/* Statistics result list */}

                      <div className="flex flex-col gap-2 flex-grow">

                        <div className="flex justify-between items-center">

                          <span className="text-xs font-semibold text-slate-700">📋 加群结果明细</span>

                          <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer select-none">

                            <input

                              type="checkbox"

                              checked={filterRestricted}

                              onChange={(e) => setFilterRestricted(e.target.checked)}

                              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-3.5 h-3.5"

                            />

                            <span className="font-medium text-amber-600">仅筛选不能直接对话的群组 ({selectedHistoryTask.results?.filter((r: any) => r.status !== 'success').length || 0})</span>

                          </label>

                        </div>



                        <div className="border border-slate-100 rounded-xl overflow-hidden flex-grow max-h-48 overflow-y-auto bg-slate-50/20">

                          {!selectedHistoryTask.results || selectedHistoryTask.results.length === 0 ? (

                            <div className="text-center py-8 text-xs text-slate-400">暂无加入结果记录。</div>

                          ) : (

                            <table className="w-full border-collapse text-left">

                              <thead>

                                <tr className="bg-slate-50 text-[10px] text-slate-400 font-bold uppercase tracking-wider border-b border-slate-100">

                                  <th className="px-4 py-2">账号</th>

                                  <th className="px-4 py-2">群组链接</th>

                                  <th className="px-4 py-2">状态</th>

                                </tr>

                              </thead>

                              <tbody className="divide-y divide-slate-50 text-xs">

                                {selectedHistoryTask.results

                                  .filter((r: any) => !filterRestricted || r.status !== 'success')

                                  .map((item: any, idx: number) => (

                                    <tr key={idx} className="hover:bg-slate-50/60 transition-colors">

                                      <td className="px-4 py-2.5 font-mono text-slate-600">{item.phone}</td>

                                      <td className="px-4 py-2.5 font-mono text-slate-500 truncate max-w-[150px]" title={item.link}>

                                        {item.link}

                                      </td>

                                      <td className="px-4 py-2.5">

                                        {item.status === 'success' && (

                                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">

                                            ✔ 可直接对话

                                          </span>

                                        )}

                                        {item.status === 'restricted' && (

                                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-100" title={item.error}>

                                            ⚠ 不能对话

                                          </span>

                                        )}

                                        {item.status === 'failed' && (

                                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-rose-50 text-rose-700 border border-rose-100" title={item.error}>

                                            ❌ 失败

                                          </span>

                                        )}

                                      </td>

                                    </tr>

                                  ))}

                              </tbody>

                            </table>

                          )}

                        </div>

                      </div>

                    </div>

                  ) : (

                    <div className="flex flex-col gap-4 flex-grow overflow-hidden">

                      {loadingHistory ? (

                        <div className="flex-grow flex items-center justify-center py-20 text-slate-400">

                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>

                          <span className="ml-2 text-xs">正在加载历史记录...</span>

                        </div>

                      ) : taskHistoryList.length === 0 ? (

                        <div className="flex-grow flex flex-col items-center justify-center py-20 text-slate-400 gap-3 border border-dashed border-slate-200 rounded-2xl bg-slate-50/10">

                          <BarChart2 className="w-10 h-10 opacity-30 text-slate-400" />

                          <div className="text-center flex flex-col gap-1">

                            <span className="text-xs font-bold text-slate-600">暂无历史任务记录</span>

                            <span className="text-[10px] text-slate-400 font-light font-sans">

                              启动并完成自动入群任务后，历史记录与执行结果将自动显示在这里。

                            </span>

                          </div>

                        </div>

                      ) : (

                        <div className="flex flex-col gap-3 overflow-y-auto max-h-[550px] pr-1">

                          {taskHistoryList.map((task) => {

                            const dateStr = task.created_at ? new Date(task.created_at).toLocaleString() : '未知时间';

                            return (

                              <div key={task.task_id} className="border border-slate-100 hover:border-blue-100 hover:bg-blue-50/5 rounded-xl p-4 transition-all flex flex-col gap-3">

                                <div className="flex justify-between items-start">

                                  <div className="flex flex-col gap-1">

                                    <div className="flex items-center gap-1.5">

                                      <span className="text-xs font-bold text-slate-700 font-mono">{dateStr}</span>

                                      <span className="bg-slate-100 px-1.5 py-0.5 rounded text-[10px] text-slate-500 font-medium">

                                        创建者: {task.owner_username || 'rosepay'}

                                      </span>

                                    </div>

                                    <span className="text-[10px] text-slate-400 font-mono truncate max-w-[200px]" title={task.task_id}>

                                      ID: {task.task_id}

                                    </span>

                                  </div>

                                  <div>

                                    {task.status === 'completed' && (

                                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100">

                                        ✔ 已完成

                                      </span>

                                    )}

                                    {task.status === 'stopped' && (

                                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-50 text-slate-500 border border-slate-200">

                                        ■ 已停止

                                      </span>

                                    )}

                                    {task.status === 'failed' && (

                                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-100">

                                        ❌ 失败

                                      </span>

                                    )}

                                    {task.status === 'running' && (

                                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-100 animate-pulse">

                                        ● 运行中

                                      </span>

                                    )}

                                  </div>

                                </div>



                                <div className="grid grid-cols-3 gap-2 bg-slate-50/60 p-2.5 rounded-lg text-center">

                                  <div>

                                    <div className="text-[10px] text-slate-400">使用账号</div>

                                    <div className="text-xs font-bold text-slate-700 mt-0.5">{task.account_count} 个</div>

                                  </div>

                                  <div>

                                    <div className="text-[10px] text-slate-400">目标链接</div>

                                    <div className="text-xs font-bold text-slate-700 mt-0.5">{task.links_count} 个</div>

                                  </div>

                                  <div>

                                    <div className="text-[10px] text-slate-400">成功加入</div>

                                    <div className="text-xs font-bold text-emerald-600 mt-0.5">

                                      {task.success_count} / {task.total_count || task.links_count}

                                    </div>

                                  </div>

                                </div>



                                <div className="flex justify-end">

                                  <button

                                    type="button"

                                    onClick={() => fetchHistoryTaskDetail(task.task_id)}

                                    className="text-xs text-blue-600 hover:text-blue-700 font-semibold flex items-center gap-1 active:scale-[0.98]"

                                  >

                                    <span>查看详情与日志</span>

                                    <span className="text-[10px]">➔</span>

                                  </button>

                                </div>

                              </div>

                            );

                          })}

                        </div>

                      )}

                    </div>

                  )}



                </div>

              </div>

            </div>

          )}



          {/* TAB 4: CAMPAIGN / MESSAGE SENDER */}

          {activeTab === 'campaign' && (

            <div className="flex flex-col gap-6">

              {/* Campaign Control Bar */}

              <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">📢 广告轰炸任务控制台</h3>

                  <p className="text-xs text-slate-400 mt-0.5 font-light">新建并管理自动化广告群发任务</p>

                </div>

                <div className="flex flex-wrap gap-2.5 items-center">

                  <label className="flex items-center gap-1.5 text-xs text-slate-600 bg-slate-50 border border-slate-200 px-3 py-2 rounded-xl cursor-pointer select-none">

                    <input

                      type="checkbox"

                      checked={showingHistoryCampaignsOnly}

                      onChange={(e) => setShowingHistoryCampaignsOnly(e.target.checked)}

                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-3.5 h-3.5"

                    />

                    <span className="font-bold text-slate-700">📜 仅显示历史记录</span>

                  </label>

                  

                  {campaignTasks.some(t => t.status === 'running') && (

                    <button

                      onClick={handleStopAllCampaignTasks}

                      className="px-4 py-2 bg-rose-50 border border-rose-100 hover:bg-rose-100 text-rose-600 rounded-xl text-xs font-bold shadow-sm transition-all flex items-center gap-1.5 active:scale-[0.98]"

                    >

                      <Pause className="w-3.5 h-3.5" />

                      <span>结束所有当前任务</span>

                    </button>

                  )}

                  

                  <button

                    onClick={() => {

                      setNewCampaignAccountId('');

                      setSelectedCampaignAccountIds([]);

                      setCampaignInputMode('library');

                      setCampaignGroupListText('');

                      setCampaignFoldersGroups({});

                      setSelectedCampaignFolderNames([]);

                      setSelectedCampaignGroupIds([]);

                      setSelectedCampaignLibraryGroupIds([]);

                      fetchGroups();

                      setShowCreateCampaignModal(true);

                    }}

                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-sm transition-all flex items-center gap-1.5 active:scale-[0.98]"

                  >

                    <PlusCircle className="w-3.5 h-3.5" />

                    <span>新建群发任务</span>

                  </button>

                </div>

              </div>



              {/* Task list preview grid */}

              {groupCampaignTasks(campaignTasks).filter(t => showingHistoryCampaignsOnly ? t.status !== 'running' : t.status === 'running').length === 0 ? (

                <div className="bg-white border border-slate-100 rounded-2xl py-20 text-center flex flex-col items-center justify-center gap-3">

                  <MessageSquare className="w-12 h-12 text-slate-300 opacity-50" />

                  <span className="text-xs text-slate-500 font-light">

                    {showingHistoryCampaignsOnly ? "暂无历史轰炸任务记录。" : "当前没有正在执行的轰炸任务，请点击“新建群发任务”启动。"}

                  </span>

                </div>

              ) : (

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

                  {groupCampaignTasks(campaignTasks)

                    .filter(t => showingHistoryCampaignsOnly ? t.status !== 'running' : t.status === 'running')

                    .map((task) => {

                      const totalSent = task.success_count + task.fail_count;

                      const successRate = totalSent > 0 ? Math.round((task.success_count / totalSent) * 100) : 100;

                      let targetGroupsList = [];

                      try {

                        targetGroupsList = JSON.parse(task.target_groups_json);

                      } catch (e) {}

                      

                      return (

                        <div 

                          key={task.id} 

                          onClick={() => {

                            setActiveCampaignTaskId(task.id);

                            fetchCampaignTaskLogs(task.task_ids);

                            setShowCampaignLogsModal(true);

                          }}

                          className="bg-white border border-slate-100 rounded-2xl p-5 shadow-xs flex flex-col gap-4 relative hover:shadow-md transition-all cursor-pointer group hover:border-slate-200"

                        >

                          {/* Card Header */}

                          <div className="flex justify-between items-start">

                            <div className="flex flex-col gap-0.5">

                              <span className="font-sans font-bold text-slate-900 text-sm">任务 #{task.id.substring(0, 8)}</span>

                              <span className="text-[10px] text-slate-400 font-light font-mono">创建于 {task.created_at}</span>

                            </div>

                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${

                              task.status === 'running' 

                                ? 'bg-emerald-50 text-emerald-700 border-emerald-100 animate-pulse'

                                : task.status === 'completed'

                                ? 'bg-blue-50 text-blue-700 border-blue-100'

                                : task.status === 'stopped'

                                ? 'bg-slate-50 text-slate-600 border-slate-200'

                                : 'bg-rose-50 text-rose-700 border-rose-100'

                            }`}>

                              {task.status === 'running' && '运行中'}

                              {task.status === 'completed' && '已完成'}

                              {task.status === 'stopped' && '已停止'}

                              {task.status === 'failed' && '执行出错'}

                            </span>

                          </div>



                          {/* Message summary */}

                          <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 text-[11px] text-slate-500 leading-normal line-clamp-3 font-medium select-none">

                            {task.message}

                          </div>



                          {/* Progress bar */}

                          <div className="flex flex-col gap-1.5">

                            <div className="flex justify-between text-[10px] font-bold text-slate-500">

                              <span>

                                {task.max_cycles === 0 

                                  ? `当前运行：第 ${task.current_cycle} 轮（无限循环）` 

                                  : `发送进度：第 ${task.current_cycle} / ${task.max_cycles} 轮`

                                }

                              </span>

                              <span>成功率: {successRate}%</span>

                            </div>

                            <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">

                              <div

                                className={`h-full transition-all duration-500 rounded-full ${

                                  task.status === 'running' ? 'bg-blue-600' : 'bg-slate-400'

                                }`}

                                style={{ 

                                  width: `${task.max_cycles > 0 ? (task.current_cycle / task.max_cycles) * 100 : 100}%` 

                                }}

                              ></div>

                            </div>

                          </div>



                          {/* Statistics grid */}

                          <div className="grid grid-cols-3 gap-2 bg-slate-50/50 p-2.5 rounded-xl border border-slate-100/30 text-center">

                            <div>

                              <span className="text-[9px] text-slate-400 block font-medium">总群组数</span>

                              <span className="text-xs font-bold text-slate-700 font-mono mt-0.5 block">{targetGroupsList.length}</span>

                            </div>

                            <div>

                              <span className="text-[9px] text-emerald-500 block font-medium">成功发送</span>

                              <span className="text-xs font-bold text-emerald-600 font-mono mt-0.5 block">{task.success_count}</span>

                            </div>

                            <div>

                              <span className="text-[9px] text-rose-500 block font-medium">发送失败</span>

                              <span className="text-xs font-bold text-rose-600 font-mono mt-0.5 block">{task.fail_count}</span>

                            </div>

                          </div>



                          {/* Parameter details badge footer */}

                          <div className="flex flex-wrap gap-1.5 text-[9px] text-slate-400 font-medium">

                            <span className="bg-slate-100 px-2 py-0.5 rounded border border-slate-200/50">

                              轮间隔: {task.round_interval_minutes}分钟

                            </span>

                            <span className="bg-slate-100 px-2 py-0.5 rounded border border-slate-200/50">

                              群间隔: {task.group_interval_seconds}秒{task.is_safety && ' (安全群发)'}

                            </span>

                            <span className="bg-blue-50 text-blue-600 px-2 py-0.5 rounded border border-blue-100/50 font-mono" title={task.phones.join(', ')}>

                              账号: {task.phones.length > 2 ? `${task.phones.slice(0, 2).join(', ')}...等${task.phones.length}个` : task.phones.join(', ')}

                            </span>

                            <span className="bg-slate-100 text-slate-500 px-2 py-0.5 rounded border border-slate-200/50">

                              创建者: {task.created_by || task.owner_username || 'rosepay'}

                            </span>

                          </div>



                          {/* Action overlay / bottom controls */}

                          <div className="flex gap-2 justify-end pt-2 border-t border-slate-50 shrink-0">

                            {task.status === 'running' && (

                              <button

                                onClick={(e) => {

                                  e.stopPropagation();

                                  if (confirm("确定要停止这个轰炸任务吗？")) {

                                    handleStopCampaignTask(task.task_ids);

                                  }

                                }}

                                className="px-3 py-1.5 bg-rose-50 border border-rose-100 hover:bg-rose-100 text-rose-600 rounded-lg text-[10px] font-bold transition-all active:scale-[0.98]"

                              >

                                🛑 停止任务

                              </button>

                            )}

                            <button

                              className="px-3 py-1.5 bg-slate-100 border border-slate-200 hover:bg-slate-200 text-slate-700 rounded-lg text-[10px] font-bold transition-all"

                            >

                              🔍 查看日志

                            </button>

                          </div>

                        </div>

                      );

                    })}

                </div>

              )}

            </div>

          )}



          {/* TAB: AD PREDEFINED TEMPLATES MANAGEMENT */}

          {activeTab === 'templates' && (

            <div className="bg-white border border-slate-100 rounded-2xl shadow-sm flex flex-col p-6 gap-6 animate-fade-in">

              <div>

                <h3 className="font-bold text-slate-900 text-base">预设广告内容库</h3>

                <p className="text-xs text-slate-400 mt-0.5">编辑与展示预设的广告内容，配置完成后可在启动群发时快捷选择。</p>

              </div>



              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                

                {/* Form to Add New Predefined Ad */}

                <div className="lg:col-span-1 flex flex-col gap-4 border border-slate-100 rounded-xl p-5 bg-slate-50/10 self-start">

                  <h4 className="font-bold text-slate-800 text-sm flex items-center gap-2 border-b border-slate-100 pb-2">

                    {editingAdId !== null ? (
                      <>
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-amber-500"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                        <span className="text-amber-700 font-bold">修改广告内容</span>
                      </>
                    ) : (
                      <>
                        <PlusCircle className="w-4 h-4 text-blue-500" />
                        <span>新增广告内容</span>
                      </>
                    )}

                  </h4>

                  

                  <div className="flex flex-col gap-1">

                    <label className="text-xs text-slate-500 font-semibold">广告描述 (简要说明)</label>

                    <input 

                      type="text"

                      value={newTemplateDesc}

                      onChange={(e) => setNewTemplateDesc(e.target.value)}

                      placeholder="例如: 官方推广话术v1"

                      className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                    />

                  </div>

                  <div className="flex flex-col gap-1">

                    <label className="text-xs text-slate-500 font-semibold">广告文本类型 (对应群组类型)</label>

                    <select

                      value={newTemplateGtype}

                      onChange={(e) => setNewTemplateGtype(e.target.value)}

                      className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500 font-medium"

                    >

                      <option value="中文长">中文长 (200字及以上)</option>

                      <option value="中文短">中文短 (200字以下)</option>

                      <option value="英文长">英文长 (200字及以上)</option>

                      <option value="英文短">英文短 (200字以下)</option>

                    </select>

                  </div>



                  <div className="flex flex-col gap-1">

                    <label className="text-xs text-slate-500 font-semibold">广告文本内容 (支持HTML)</label>

                    <textarea

                      value={newTemplateContent}

                      onChange={(e) => setNewTemplateContent(e.target.value)}

                      placeholder="请输入具体的广告内容文案..."

                      className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500 h-32 resize-none font-medium leading-relaxed"

                    ></textarea>

                  </div>



                  {editingAdId !== null ? (
                    <div className="flex gap-2">
                      <button
                        onClick={handleUpdatePredefinedAd}
                        disabled={!newTemplateDesc.trim() || !newTemplateContent.trim()}
                        className="flex-grow py-2 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-400 text-white text-xs font-bold rounded-lg transition-all shadow-sm active:scale-[0.98]"
                      >
                        保存修改
                      </button>
                      <button
                        onClick={() => {
                          setEditingAdId(null);
                          setNewTemplateDesc('');
                          setNewTemplateContent('');
                          setNewTemplateGtype('英文短');
                        }}
                        className="px-3 py-2 bg-slate-150 hover:bg-slate-200 text-slate-600 text-xs font-bold rounded-lg transition-all"
                      >
                        取消
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={handleCreatePredefinedAd}
                      disabled={!newTemplateDesc.trim() || !newTemplateContent.trim()}
                      className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-xs font-bold rounded-lg transition-all shadow-sm active:scale-[0.98]"
                    >
                      添加并保存
                    </button>
                  )}

                </div>



                {/* List of Existing Predefined Ads */}

                <div className="lg:col-span-2 flex flex-col gap-4">

                  <h4 className="font-bold text-slate-800 text-sm flex items-center gap-2 border-b border-slate-100 pb-2">

                    <FileText className="w-4 h-4 text-blue-500" />

                    <span>已有广告内容列表 ({adTemplates.length})</span>

                  </h4>



                  {adTemplates.length === 0 ? (

                    <div className="text-slate-400 text-center py-12 border border-dashed border-slate-200 rounded-xl bg-slate-50/20 text-xs">

                      目前没有任何预设广告语，请在左侧表单中进行添加。

                    </div>

                  ) : (

                    <div className="grid grid-cols-1 gap-4 max-h-[500px] overflow-y-auto pr-1">

                      {adTemplates.map((tpl) => (

                        <div key={tpl.id} className={`relative border rounded-xl p-4 bg-white hover:shadow-xs transition-all flex flex-col gap-2 ${editingAdId === tpl.id ? 'border-amber-400 ring-2 ring-amber-400/10 bg-amber-50/5' : 'border-slate-150 hover:border-slate-200'}`}>

                          <div className="flex justify-between items-start gap-2">

                            <div className="flex flex-wrap items-center gap-1.5">

                              <span className="font-bold text-slate-800 text-xs px-2.5 py-1 bg-blue-50 text-blue-700 rounded-md border border-blue-100">

                                {tpl.description}

                              </span>

                              {tpl.group_type && (
                                <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                                  tpl.group_type.includes('长')
                                    ? 'bg-purple-50 text-purple-600 border-purple-100'
                                    : 'bg-indigo-50 text-indigo-600 border-indigo-100'
                                }`}>
                                  🏷️ {tpl.group_type}
                                </span>
                              )}

                            </div>

                            <div className="flex items-center gap-1">

                              <button
                                onClick={() => {
                                  setEditingAdId(tpl.id);
                                  setNewTemplateDesc(tpl.description);
                                  setNewTemplateContent(tpl.content);
                                  setNewTemplateGtype(tpl.group_type || '英文短');
                                }}
                                className="w-6 h-6 hover:bg-amber-50 text-slate-400 hover:text-amber-600 rounded-full flex items-center justify-center transition-colors"
                                title="编辑广告内容"
                              >
                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                              </button>

                              <button

                                onClick={() => handleDeletePredefinedAd(tpl.id)}

                                className="w-6 h-6 hover:bg-rose-50 text-slate-400 hover:text-rose-600 rounded-full flex items-center justify-center transition-colors"

                                title="删除广告内容"

                              >

                                <X className="w-3.5 h-3.5" />

                              </button>

                            </div>

                          </div>

                          <pre className="text-xs text-slate-600 font-mono whitespace-pre-wrap leading-relaxed bg-slate-50 p-2.5 rounded-lg border border-slate-100">

                            {tpl.content}

                          </pre>

                        </div>

                      ))}

                    </div>

                  )}

                </div>



              </div>

            </div>

          )}





          {/* TAB 5: TASK LOGS Chronological */}

          {activeTab === 'logs' && (

            <div className="bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden flex flex-col">

              <div className="p-6 border-b border-slate-50 bg-slate-50/20 flex justify-between items-center">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">系统及群发日志明细</h3>

                  <p className="text-xs text-slate-400 mt-0.5">全局任务活动历史记录</p>

                </div>

                <button 

                  onClick={() => setLogs([])}

                  className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg text-xs font-semibold transition-colors"

                >

                  ❌ 清除日志

                </button>

              </div>



              <div className="p-6 flex flex-col gap-3 font-mono text-xs">

                {logs.length === 0 ? (

                  <div className="text-slate-400 text-center py-12">暂无历史活动记录。</div>

                ) : (

                  logs.map((log, index) => (

                    <div key={index} className="flex gap-4 p-4 border border-slate-100 rounded-xl hover:border-slate-200 shadow-sm transition-all bg-slate-50/10">

                      <div className="text-slate-400 font-semibold">{log.time}</div>

                      <div className="w-20">

                        <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[9px] font-semibold border border-slate-200">

                          {log.folder}

                        </span>

                      </div>

                      <div className="flex-grow">

                        <div className="font-semibold text-slate-800">{log.action}：{log.title}</div>

                        <div className="text-slate-500 mt-0.5">账号: {log.phone} | 详情: {log.detail}</div>

                      </div>

                      <div>

                        <span className={`px-2.5 py-0.5 rounded text-[10px] font-semibold ${

                          log.status === 'success' 

                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' 

                            : log.status === 'warning' 

                            ? 'bg-amber-50 text-amber-700 border border-amber-100' 

                            : 'bg-rose-50 text-rose-700 border border-rose-100'

                        }`}>

                          {log.status === 'success' && '成功'}

                          {log.status === 'warning' && '跳过'}

                          {log.status === 'error' && '错误'}

                        </span>

                      </div>

                    </div>

                  ))

                )}

              </div>

            </div>

          )}



          



          {/* TAB 6: SETTINGS FOR CONNECTION & PROXY */}

          {activeTab === 'settings' && (

            <div className="bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden flex flex-col p-6 gap-6">

              <div>

                <h3 className="font-bold text-slate-900 text-base">系统常规设置</h3>

                <p className="text-xs text-slate-400 mt-0.5">在这里配置本地运行所需的各类连接凭证和代理设定</p>

              </div>



              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

                

                {/* Proxy Form */}

                <div className="flex flex-col gap-4 border border-slate-100 rounded-xl p-5 bg-slate-50/10">

                  <h4 className="font-bold text-slate-800 text-sm flex items-center gap-2 border-b border-slate-100 pb-2">

                    🌐 网络代理配置 (Proxy)

                  </h4>



                  <div className="form-group mt-2">

                    <label className="checkbox-container">

                      <input 

                        type="checkbox" 

                        checked={proxyEnabled}

                        onChange={(e) => setProxyEnabled(e.target.checked)}

                      />

                      <span className="text-sm text-slate-700 font-semibold">启用全局网络代理 (推荐)</span>

                    </label>

                  </div>



                  <div className="form-row">

                    <div className="form-group">

                      <label className="text-xs text-slate-500">代理协议</label>

                      <select className="bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs">

                        <option value="http">HTTP</option>

                        <option value="socks5">SOCKS5</option>

                        <option value="socks4">SOCKS4</option>

                      </select>

                    </div>

                    <div className="form-group">

                      <label className="text-xs text-slate-500">主机地址 / IP</label>

                      <input 

                        type="text" 

                        value={proxyHost}

                        onChange={(e) => setProxyHost(e.target.value)}

                        className="bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs"

                      />

                    </div>

                  </div>



                  <div className="form-row">

                    <div className="form-group">

                      <label className="text-xs text-slate-500">代理端口</label>

                      <input 

                        type="number" 

                        value={proxyPort}

                        onChange={(e) => { const val = e.target.value; setProxyPort(val === '' ? '' : parseInt(val) || 0); }}

                        className="bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs"

                      />

                    </div>

                    <div className="form-group">

                      <label className="text-xs text-slate-500">账号 (可空)</label>

                      <input 

                        type="text" 

                        value={proxyUser}

                        onChange={(e) => setProxyUser(e.target.value)}

                        className="bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs"

                      />

                    </div>

                  </div>



                  <div className="form-group">

                    <label className="text-xs text-slate-500">密码 (可空)</label>

                    <input 

                      type="password" 

                      value={proxyPass}

                      onChange={(e) => setProxyPass(e.target.value)}

                      className="bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs"

                    />

                  </div>



                  <button 

                    onClick={() => {

                      setToastText('代理配置已更新并保存');

                      setTimeout(() => setToastText(''), 2000);

                    }}

                    className="self-start px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-all mt-2"

                  >

                    💾 保存代理设置

                  </button>

                </div>



                {/* API keys credentials */}

                <div className="flex flex-col gap-4 border border-slate-100 rounded-xl p-5 bg-slate-50/10">

                  <h4 className="font-bold text-slate-800 text-sm flex items-center gap-2 border-b border-slate-100 pb-2">

                    🔑 Telegram API 应用凭证 (Apps)

                  </h4>



                  <div className="form-group mt-2">

                    <label className="text-xs text-slate-500">登录认证模式 (auth_mode)</label>

                    <select 

                      value={authMode}

                      onChange={(e) => setAuthMode(e.target.value as any)}

                      className="bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs"

                    >

                      <option value="builtin">builtin_telegram_desktop (内置官方模板)</option>

                      <option value="api_hash">api_id_hash (使用个人开发者凭证)</option>

                    </select>

                  </div>



                  {authMode === 'api_hash' && (

                    <div className="flex flex-col gap-4 transition-all">

                      <div className="form-group">

                        <label className="text-xs text-slate-500">api_id</label>

                        <input 

                          type="text" 

                          value={apiId}

                          onChange={(e) => setApiId(e.target.value)}

                          placeholder="例如: 123456"

                          className="bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs font-mono"

                        />

                      </div>

                      <div className="form-group">

                        <label className="text-xs text-slate-500">api_hash</label>

                        <input 

                          type="text" 

                          value={apiHash}

                          onChange={(e) => setApiHash(e.target.value)}

                          placeholder="例如: 84b3d87a..."

                          className="bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs font-mono"

                        />

                      </div>

                    </div>

                  )}



                  {authMode === 'builtin' && (

                    <div className="bg-blue-50/40 border border-blue-100 rounded-lg p-4 text-xs text-blue-800 font-light leading-relaxed">

                      💡 <strong>内置模板模式：</strong>程序将模拟官方标准的 Telegram Desktop 应用，免除您在 <code>my.telegram.org</code> 申请开发者 App 凭证的繁琐步骤。

                    </div>

                  )}



                  <button 

                    onClick={() => {

                      setToastText('系统凭证配置已生效');

                      setTimeout(() => setToastText(''), 2000);

                    }}

                    className="self-start px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-all mt-2"

                  >

                    💾 保存 API 凭证

                  </button>

                </div>



              </div>

            </div>

          )}



          



                    {/* TAB 8: SYSTEM USER & COMPANY MANAGEMENT */}

          {activeTab === 'users' && userRole === 'admin' && (

            <div className="bg-white border border-slate-100 rounded-2xl shadow-sm flex flex-col">

              {/* Tab Header with Sub-tabs Toggle */}

              <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/20 flex flex-wrap justify-between items-center gap-4">

                <div className="flex gap-2 p-1 bg-slate-100 rounded-xl">

                  <button

                    onClick={() => setSystemTabSubView('users')}

                    className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${systemTabSubView === 'users' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}

                  >

                    系统用户管理

                  </button>

                  <button

                    onClick={() => setSystemTabSubView('companies')}

                    className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${systemTabSubView === 'companies' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}

                  >

                    公司管理

                  </button>

                </div>

                {systemTabSubView === 'users' ? (

                  <button 

                    onClick={() => setShowAddUserModal(true)}

                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-sm transition-all flex items-center gap-1.5 active:scale-[0.98]"

                  >

                    <PlusCircle className="w-4 h-4" />

                    <span>添加用户</span>

                  </button>

                ) : (

                  <button 

                    onClick={() => setShowAddCompanyModal(true)}

                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-sm transition-all flex items-center gap-1.5 active:scale-[0.98]"

                  >

                    <PlusCircle className="w-4 h-4" />

                    <span>添加公司</span>

                  </button>

                )}

              </div>



              {systemTabSubView === 'users' ? (

                <>

                  <div className="p-6 pb-2">

                    <p className="text-xs text-slate-400">在此可以配置不同的系统用户，为操作员分配对应的管理权限及所属公司。</p>

                  </div>

                  <div className="overflow-x-auto">

                    <table className="w-full text-left border-collapse">

                      <thead>

                        <tr className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-semibold uppercase text-slate-400 tracking-wider">

                          <th className="py-4 px-6">ID</th>

                          <th className="py-4 px-6">用户名</th>

                          <th className="py-4 px-6">所属公司</th>

                          <th className="py-4 px-6">角色权限</th>

                          <th className="py-4 px-6">通知绑定</th>

                          <th className="py-4 px-6">创建时间</th>

                          <th className="py-4 px-6 text-right">操作</th>

                        </tr>

                      </thead>

                      <tbody>

                        {usersList.length === 0 ? (

                          <tr>

                            <td colSpan={7} className="py-8 text-center text-slate-400 text-xs font-light">

                              暂无用户数据。

                            </td>

                          </tr>

                        ) : (

                          usersList.map((user) => {

                            const telegramContact = (user.telegram_contact || '').trim();

                            const telegramHref = telegramContact ? `https://t.me/${telegramContact.replace(/^@/, '')}` : '';

                            return (

                            <tr key={user.id} className="border-b border-slate-50 text-sm text-slate-700 hover:bg-slate-50/40 transition-colors">

                              <td className="py-4 px-6 font-mono text-xs text-slate-500">{user.id}</td>

                              <td className="py-4 px-6 font-semibold text-slate-900">{user.username}</td>

                              <td className="py-4 px-6">

                                <span className="px-2 py-0.5 bg-indigo-50 text-indigo-600 border border-indigo-100 rounded text-[10px] font-semibold">

                                  {user.company || 'admin'}

                                </span>

                              </td>

                              <td className="py-4 px-6">

                                {user.role === 'admin' ? (

                                  <span className="px-2.5 py-0.5 bg-blue-50 text-blue-600 rounded-full text-[10px] font-bold border border-blue-100">

                                    系统管理员

                                  </span>

                                ) : (

                                  <span className="px-2.5 py-0.5 bg-slate-100 text-slate-600 rounded-full text-[10px] font-medium border border-slate-200">

                                    普通操作员

                                  </span>

                                )}

                              </td>

                              <td className="py-4 px-6 min-w-[180px]">

                                <div className="flex flex-col gap-1 text-[11px]">

                                  {telegramContact ? (

                                    <a

                                      href={telegramHref}

                                      target="_blank"

                                      rel="noreferrer"

                                      className="font-mono text-blue-600 hover:text-blue-700 hover:underline truncate max-w-[180px]"

                                      title={telegramContact}

                                    >

                                      {telegramContact}

                                    </a>

                                  ) : (

                                    <span className="text-slate-300">未绑定电报号</span>

                                  )}

                                </div>

                              </td>

                              <td className="py-4 px-6 text-xs text-slate-500 font-mono">

                                {new Date(user.created_at).toLocaleString('zh-CN')}

                              </td>

                              <td className="py-4 px-6 text-right">

                                <button 

                                  onClick={() => {

                                    setEditUserTarget(user);

                                    setEditUserRole(user.role === 'admin' ? 'admin' : 'user');

                                    setEditUserCompany(user.company || 'admin');

                                    setEditUserPassword('');

                                    setEditUserTelegramContact(user.telegram_contact || '');

                                    setShowEditUserModal(true);

                                  }}

                                  className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors mr-1"

                                  title="编辑用户"

                                >

                                  <Edit className="w-4 h-4" />

                                </button>

                                <button 

                                  onClick={() => handleDeleteUser(user.id, user.username)}

                                  disabled={user.username === currentUsername}

                                  className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-slate-400"

                                  title={user.username === currentUsername ? '无法删除当前登录的用户' : '删除用户'}

                                >

                                  <Trash2 className="w-4 h-4" />

                                </button>

                              </td>

                            </tr>

                            );

                          })

                        )}

                      </tbody>

                    </table>

                  </div>

                </>

              ) : (

                <>

                  <div className="p-6 pb-2">

                    <p className="text-xs text-slate-400">在此管理公司主体。系统用户与 Telegram 账号绑定至特定公司，以实现数据隔离。</p>

                  </div>

                  <div className="overflow-x-auto">

                    <table className="w-full text-left border-collapse">

                      <thead>

                        <tr className="border-b border-slate-100 bg-slate-50/50 text-[11px] font-semibold uppercase text-slate-400 tracking-wider">

                          <th className="py-4 px-6">ID</th>

                          <th className="py-4 px-6">公司名称</th>

                          <th className="py-4 px-6">创建时间</th>

                          <th className="py-4 px-6 text-right">操作</th>

                        </tr>

                      </thead>

                      <tbody>

                        {companiesList.length === 0 ? (

                          <tr>

                            <td colSpan={4} className="py-8 text-center text-slate-400 text-xs font-light">

                              暂无公司数据。

                            </td>

                          </tr>

                        ) : (

                          companiesList.map((company) => (

                            <tr key={company.id} className="border-b border-slate-50 text-sm text-slate-700 hover:bg-slate-50/40 transition-colors">

                              <td className="py-4 px-6 font-mono text-xs text-slate-500">{company.id}</td>

                              <td className="py-4 px-6 font-semibold text-slate-900">{company.name}</td>

                              <td className="py-4 px-6 text-xs text-slate-500 font-mono">

                                {company.created_at ? new Date(company.created_at).toLocaleString('zh-CN') : '-'}

                              </td>

                              <td className="py-4 px-6 text-right flex justify-end gap-2">

                                <button

                                  onClick={() => {

                                    setEditCompanyTarget(company);

                                    setEditCompanyNameValue(company.name);

                                    setShowEditCompanyModal(true);

                                  }}

                                  className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"

                                  title="编辑公司"

                                >

                                  <Edit className="w-4 h-4" />

                                </button>

                                <button 

                                  onClick={() => handleDeleteCompany(company.id, company.name)}

                                  disabled={company.name === 'admin'}

                                  className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-slate-400"

                                  title={company.name === 'admin' ? '无法删除admin' : '删除公司'}

                                >

                                  <Trash2 className="w-4 h-4" />

                                </button>

                              </td>

                            </tr>

                          ))

                        )}

                      </tbody>

                    </table>

                  </div>

                </>

              )}

            </div>

          )}




          {activeTab === 'bot_auth' && userRole === 'admin' && (
            <div className="flex flex-col gap-6 animate-in fade-in duration-300">
              <div className="bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-50 bg-slate-50/20 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  <div>
                    <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                      <Bot className="w-4 h-4 text-amber-500" />
                      Bot 节点权限管理
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">管理 AI 助手、翻译助手等 Bot 节点，以及每个 Bot 专属授权账号、中转群和首问自动回复模板。</p>
                  </div>
                  <div className="flex flex-wrap gap-2.5 items-center">
                    <button onClick={() => refreshBotPermissionPage()} className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold flex items-center gap-1.5">
                      <RefreshCw className={`w-3.5 h-3.5 ${botsLoading ? 'animate-spin' : ''}`} />
                      刷新
                    </button>
                    <button onClick={openCreateBotNodeModal} className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-sm">
                      <PlusCircle className="w-3.5 h-3.5" />
                      新增电报 Bot 节点
                    </button>
                  </div>
                </div>

                <div className="p-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {managedBots.length === 0 ? (
                    <div className="col-span-full py-12 text-center text-xs text-slate-400 bg-slate-50/50 border border-dashed border-slate-200 rounded-2xl">
                      暂无 Bot 节点，请先新增或检查服务器 Bot 配置。
                    </div>
                  ) : managedBots.map((bot) => (
                    <div key={bot.id || bot.bot_type} className="bg-white border border-slate-100 rounded-2xl p-5 shadow-xs hover:shadow-sm transition-all flex flex-col gap-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-black text-slate-900 text-sm truncate">{bot.title || bot.bot_username || bot.bot_type}</span>
                            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${bot.is_active ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-slate-100 text-slate-400 border-slate-200'}`}>{bot.is_active ? '启用' : '停用'}</span>
                          </div>
                          <div className="text-[11px] text-blue-600 font-mono mt-1 truncate">@{(bot.bot_username || '').replace(/^@+/, '')}</div>
                          <div className="text-[10px] text-slate-400 font-mono mt-1">{bot.bot_type}</div>
                        </div>
                        <Bot className="w-5 h-5 text-amber-500 shrink-0" />
                      </div>
                      <p className="text-[11px] text-slate-400 leading-relaxed min-h-[34px] line-clamp-2">{bot.description || '暂无功能描述'}</p>
                      <div className="grid grid-cols-2 gap-2 text-[10px]">
                        <div className="rounded-xl bg-slate-50 border border-slate-100 px-3 py-2">
                          <div className="text-slate-400 font-bold">关联数量</div>
                          <div className="text-slate-800 font-mono font-black mt-1">{bot.linked_accounts_count ?? bot.authorization_count ?? 0}</div>
                        </div>
                        <div className="rounded-xl bg-slate-50 border border-slate-100 px-3 py-2">
                          <div className="text-slate-400 font-bold">创建时间</div>
                          <div className="text-slate-700 font-mono font-semibold mt-1 truncate">{bot.created_at ? new Date(bot.created_at).toLocaleDateString() : '-'}</div>
                        </div>
                      </div>
                      <div className="flex gap-2 pt-1">
                        {isTranslateBotType(bot.bot_type) ? (
                          <button onClick={() => openEditBotNodeModal(bot, 'auth')} className="flex-1 px-3 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-[11px] font-black transition-all active:scale-[0.98]">查看绑定账号</button>
                        ) : (
                          <>
                            <button onClick={() => openEditBotNodeModal(bot, 'auth')} className="flex-1 px-3 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-[11px] font-black transition-all active:scale-[0.98]">专属授权账号与中转群</button>
                            <button onClick={() => openEditBotNodeModal(bot, 'reply')} className="px-3 py-2 border border-slate-200 hover:bg-slate-50 text-slate-600 rounded-xl text-[11px] font-bold transition-colors">自动回复</button>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'permissions' && userRole === 'admin' && (

            <div className="bg-white border border-slate-100 rounded-2xl shadow-sm flex flex-col p-6 gap-6">

              <div>

                <h3 className="font-bold text-slate-900 text-base">系统权限管理</h3>

                <p className="text-xs text-slate-400 mt-0.5">配置系统不同角色能够访问的菜单页面，防止越权操作。</p>

              </div>



              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                {rolePermissions.map((rp) => (

                  <div key={rp.role} className="bg-slate-50/50 border border-slate-100 rounded-2xl p-5 flex flex-col gap-4">

                    <div className="flex justify-between items-center border-b border-slate-100 pb-3">

                      <div>

                        <span className="font-bold text-slate-900 text-sm">

                          {rp.role === 'admin' ? '系统管理员 (admin)' : '普通操作员 (user)'}

                        </span>

                        <p className="text-[10px] text-slate-400 mt-0.5">配置此角色在侧边栏可见的菜单项</p>

                      </div>

                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${

                        rp.role === 'admin' 

                          ? 'bg-blue-50 text-blue-700 border border-blue-100' 

                          : 'bg-slate-100 text-slate-500 border border-slate-200'

                      }`}>

                        {rp.role === 'admin' ? '全部权限' : '自定义权限'}

                      </span>

                    </div>



                    <div className="flex flex-col gap-2.5">

                      {[

                        { id: 'login', name: '账号登录' },

                        { id: 'accounts', name: '账号管理' },

                        { id: 'groups', name: '群组维护' },

                        { id: 'join', name: '自动入群' },

                        { id: 'campaign', name: '轰炸他们' },

                        { id: 'templates', name: '广告内容' },

                        { id: 'logs', name: '任务日志' },

                        { id: 'settings', name: '设置' },

                        { id: 'users', name: '系统管理' },

                        { id: 'permissions', name: '权限管理' },

                        { id: 'bot_auth', name: 'Bot 权限管理' }

                      ].map((tab) => {

                        const isSelfLockout = rp.role === 'admin' && (tab.id === 'users' || tab.id === 'permissions');

                        const isChecked = rp.allowed_tabs.includes(tab.id) || isSelfLockout;



                        return (

                          <label 

                            key={tab.id} 

                            className={`flex items-center justify-between p-2.5 rounded-lg border text-xs cursor-pointer select-none transition-all ${

                              isChecked 

                                ? 'border-blue-100 bg-blue-50/20 text-slate-800' 

                                : 'border-slate-100 bg-white text-slate-500 hover:bg-slate-50'

                            } ${isSelfLockout ? 'opacity-60 cursor-not-allowed bg-slate-100/50' : ''}`}

                          >

                            <div className="flex items-center gap-2">

                              <input 

                                type="checkbox" 

                                checked={isChecked}

                                disabled={isSelfLockout}

                                onChange={(e) => {

                                  if (isSelfLockout) return;

                                  const checked = e.target.checked;

                                  setRolePermissions(prev => prev.map(item => {

                                    if (item.role === rp.role) {

                                      const updatedTabs = checked 

                                        ? [...item.allowed_tabs, tab.id]

                                        : item.allowed_tabs.filter(id => id !== tab.id);

                                      return { ...item, allowed_tabs: updatedTabs };

                                    }

                                    return item;

                                  }));

                                }}

                                className="rounded text-blue-600 focus:ring-blue-500/20 border-slate-300 cursor-pointer disabled:cursor-not-allowed"

                              />

                              <span className="font-semibold">{tab.name}</span>

                            </div>

                            <span className="text-[10px] font-mono text-slate-400">{tab.id}</span>

                          </label>

                        );

                      })}

                    </div>



                    <button

                      onClick={async () => {

                        setSavingPermissions(true);

                        const backendUrl = BASE_URL;

                        try {

                          const res = await fetch(`${backendUrl}/api/admin/permissions`, {

                            method: 'POST',

                            headers: { 'Content-Type': 'application/json' },

                            body: JSON.stringify({

                              role: rp.role,

                              allowed_tabs: rp.allowed_tabs

                            })

                          });

                          const data = await res.json();

                          if (res.ok) {

                            setToastText(`角色 ${rp.role === 'admin' ? '系统管理员' : '普通操作员'} 的权限保存成功`);

                            setTimeout(() => setToastText(''), 2000);

                            if (rp.role === userRole) {

                              setAllowedTabs([...rp.allowed_tabs, 'finder', 'expansion']);

                            }

                          } else {

                            alert(`保存失败: ${data.detail}`);

                          }

                        } catch (err: any) {

                          alert(`保存异常: ${err.message}`);

                        } finally {

                          setSavingPermissions(false);

                        }

                      }}

                      disabled={savingPermissions}

                      className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-xl font-bold text-xs shadow-md transition-all active:scale-[0.98] mt-2 flex items-center justify-center gap-1.5"

                    >

                      {savingPermissions ? '正在保存...' : '💾 保存权限规则'}

                    </button>

                  </div>

                ))}

              </div>



              <div className="bg-amber-50/50 border border-amber-100 rounded-xl p-4 text-xs text-amber-800 flex flex-col gap-1 leading-normal">

                <span className="font-bold flex items-center gap-1">

                  <Shield className="w-3.5 h-3.5" /> 安全提示

                </span>

                <span>1. 系统管理员拥有所有菜单权限，无法取消 系统管理(users) 与 权限管理(permissions) 的勾选，以防管理员将自己锁死。</span>

                <span>2. 保存某角色的权限后，系统将实时更新该角色名下的所有操作员菜单。</span>

              </div>

            </div>

          )}



          {activeTab === 'finder' && (
            <div className="flex flex-col gap-6 w-full animate-fade-in">
              
              {/* Row 1: Search Console (Left) and Logs (Right) */}
              <div className="flex flex-col lg:flex-row gap-6 items-stretch w-full">
                
                {/* Search Console */}
                <div className="w-full lg:w-[380px] bg-white border border-slate-100 rounded-2xl p-6 shadow-sm flex flex-col gap-4">
                  <div>
                    <h3 className="font-bold text-slate-900 text-base flex items-center gap-1.5">
                      <Search className="w-4 h-4 text-blue-500" />
                      新建搜群任务
                    </h3>
                    <p className="text-xs text-slate-400 mt-1">输入行业关键词，自动从公开目录和网页搜寻群组并进行 AI 评估分析。</p>
                  </div>

                  {/* AI Config status container */}
                  <div className="flex flex-col gap-2.5 bg-slate-50 border border-slate-100 rounded-xl p-3">
                    <div className="text-[11px] font-bold text-slate-700 flex items-center gap-1.5 border-b border-slate-100 pb-1.5">
                      <Key className="w-3.5 h-3.5 text-blue-500" />
                      AI 质量评估引擎配置
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2">
                      {/* Gemini Status Card */}
                      <div className="bg-white border border-slate-150 rounded-lg p-2.5 flex flex-col justify-between gap-1 shadow-xs">
                        <div className="flex justify-between items-center text-[10px] font-bold text-slate-500">
                          <span>Gemini</span>
                          <span className={`px-1.5 py-0.2 rounded-full text-[9px] font-black ${hasGeminiKey ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'}`}>
                            {hasGeminiKey ? '已配' : '未配'}
                          </span>
                        </div>
                        {hasGeminiKey && (
                          <div className="text-[9px] text-slate-400 font-mono mt-0.5 truncate select-none" title={geminiKeyPreview}>
                            {geminiKeyPreview}
                          </div>
                        )}
                        <button
                          onClick={() => {
                            setNewGeminiKey('');
                            setShowGeminiConfigModal(true);
                          }}
                          className="w-full py-1 bg-blue-50 hover:bg-blue-100 text-blue-600 font-bold rounded text-[10px] transition-all mt-1"
                        >
                          ⚙️ 配置
                        </button>
                      </div>

                      {/* DeepSeek Status Card */}
                      <div className="bg-white border border-slate-150 rounded-lg p-2.5 flex flex-col justify-between gap-1 shadow-xs">
                        <div className="flex justify-between items-center text-[10px] font-bold text-slate-500">
                          <span>DeepSeek</span>
                          <span className={`px-1.5 py-0.2 rounded-full text-[9px] font-black ${hasDeepSeekKey ? 'bg-cyan-50 text-cyan-600' : 'bg-rose-50 text-rose-600'}`}>
                            {hasDeepSeekKey ? '已配' : '未配'}
                          </span>
                        </div>
                        {hasDeepSeekKey && (
                          <div className="text-[9px] text-slate-400 font-mono mt-0.5 truncate select-none" title={deepSeekKeyPreview}>
                            {deepSeekKeyPreview}
                          </div>
                        )}
                        <button
                          onClick={() => {
                            setNewDeepSeekKey('');
                            setShowDeepSeekConfigModal(true);
                          }}
                          className="w-full py-1 bg-cyan-50 hover:bg-cyan-100 text-cyan-600 font-bold rounded text-[10px] transition-all mt-1"
                        >
                          ⚙️ 配置
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Form Fields */}
                  <div className="flex flex-col gap-3">
                    <label className="text-xs font-semibold text-slate-500">搜寻关键词 (一行一个)</label>
                    <textarea
                      value={scrapedKeywords}
                      onChange={(e) => setScrapedKeywords(e.target.value)}
                      placeholder="例如:&#10;india chat&#10;delhi otc&#10;mumbai trade"
                      disabled={isSearchingScraped}
                      rows={4}
                      className="w-full border border-slate-200 rounded-xl p-3 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none resize-none"
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-semibold text-slate-500">最少成员数</label>
                    <input
                      type="number"
                      value={scrapedMinMembers}
                      onChange={(e) => setScrapedMinMembers(Number(e.target.value))}
                      disabled={isSearchingScraped}
                      className="w-full border border-slate-200 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none focus:border-blue-500 bg-slate-50 focus:bg-white"
                    />
                  </div>

                  {/* Execution Parameters (scrapedAutoJoin) */}
                  <div className="bg-slate-50 border border-slate-100 rounded-xl p-4 flex flex-col gap-3">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                        <User className="w-3.5 h-3.5 text-blue-500" />
                        执行参数
                      </span>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={scrapedAutoJoin}
                          onChange={(e) => setScrapedAutoJoin(e.target.checked)}
                          disabled={isSearchingScraped}
                          className="sr-only peer"
                        />
                        <div className="w-8 h-4 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3 after:w-3.5 after:transition-all peer-checked:bg-blue-600"></div>
                      </label>
                    </div>

                    {scrapedAutoJoin && (
                      <div className="flex flex-col gap-3 pt-2 border-t border-slate-200/60 animate-fade-in">
                        <div className="flex flex-col gap-1.5">
                          <div className="flex justify-between items-center">
                            <label className="text-[11px] font-semibold text-slate-500">自动保存最低分门槛</label>
                            <span className="text-[11px] font-bold text-blue-600">{scrapedAutoJoinMinScore} 分</span>
                          </div>
                          <input
                            type="range"
                            min="10"
                            max="100"
                            step="5"
                            value={scrapedAutoJoinMinScore}
                            onChange={(e) => setScrapedAutoJoinMinScore(Number(e.target.value))}
                            disabled={isSearchingScraped}
                            className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                          />
                        </div>

                        <div className="grid grid-cols-3 gap-2">
                          <div className="flex flex-col gap-1">
                            <label className="text-[10px] font-semibold text-slate-400">单轮搜寻限制 (个)</label>
                            <input
                              type="number"
                              min="1"
                              value={scrapedGroupsPerRound}
                              onChange={(e) => setScrapedGroupsPerRound(Number(e.target.value))}
                              disabled={isSearchingScraped}
                              className="w-full border border-slate-200 rounded-lg px-2 py-1 text-[11px] focus:ring-1 focus:ring-blue-500 focus:outline-none bg-white"
                            />
                          </div>
                          <div className="flex flex-col gap-1">
                            <label className="text-[10px] font-semibold text-slate-400">轮次间隔 (分)</label>
                            <input
                              type="number"
                              min="1"
                              value={scrapedRoundInterval}
                              onChange={(e) => setScrapedRoundInterval(Number(e.target.value))}
                              disabled={isSearchingScraped}
                              className="w-full border border-slate-200 rounded-lg px-2 py-1 text-[11px] focus:ring-1 focus:ring-blue-500 focus:outline-none bg-white"
                            />
                          </div>
                          <div className="flex flex-col gap-1">
                            <label className="text-[10px] font-semibold text-slate-400">最大限制 (轮)</label>
                            <input
                              type="text"
                              value={scrapedMaxRounds === '' ? '' : scrapedMaxRounds}
                              onChange={(e) => {
                                const val = e.target.value;
                                setScrapedMaxRounds(val === '' ? '' : parseInt(val) || '');
                              }}
                              placeholder="无限制"
                              disabled={isSearchingScraped}
                              className="w-full border border-slate-200 rounded-lg px-2 py-1 text-[11px] focus:ring-1 focus:ring-blue-500 focus:outline-none bg-white"
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Action Buttons */}
                  <div className="mt-1">
                    {isSearchingScraped ? (
                      <button
                        onClick={stopScrapedSearchTask}
                        className="w-full py-2.5 bg-rose-600 hover:bg-rose-700 active:scale-[0.98] text-white rounded-xl font-bold text-xs shadow-sm shadow-rose-600/10 transition-all flex items-center justify-center gap-1.5"
                      >
                        <span className="w-2 h-2 bg-white rounded-full animate-ping"></span>
                        停止搜寻任务
                      </button>
                    ) : (
                      <button
                        onClick={startScrapedSearchTask}
                        disabled={!hasGeminiKey}
                        className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 active:scale-[0.98] text-white rounded-xl font-bold text-xs shadow-sm shadow-blue-600/10 transition-all flex items-center justify-center gap-1.5"
                      >
                        <Play className="w-3.5 h-3.5 fill-white" />
                        开始搜寻并智能分析
                      </button>
                    )}
                  </div>
                </div>

                {/* Logs Console */}
                <div className="flex-1 bg-white border border-slate-100 rounded-2xl p-6 shadow-sm flex flex-col gap-3 min-h-[350px]">
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                        <FileText className="w-4 h-4 text-blue-500" />
                        AI 思考与运行日志
                      </h3>
                      <p className="text-[11px] text-slate-400 mt-0.5">实时展示 Agent 搜群状态、AI 评分打分等思考过程。</p>
                    </div>
                    {isSearchingScraped && (
                      <span className="text-[11px] text-slate-400 bg-slate-100 px-2 py-0.5 rounded font-mono">
                        任务进度: {scrapedTaskProgress.current}/{scrapedTaskProgress.total}
                      </span>
                    )}
                  </div>
                  <div className="flex-1 bg-slate-900 border border-slate-900 rounded-2xl p-4 font-mono text-[10px] text-emerald-400 overflow-y-auto flex flex-col gap-1.5 leading-relaxed shadow-inner min-h-[250px]">
                    {scrapedTaskLogs.length === 0 ? (
                      <div className="text-slate-500 text-center py-20">等待 Agent 任务启动输出日志...</div>
                    ) : (
                      scrapedTaskLogs.map((logStr, lIdx) => {
                        let isAiThought = logStr.includes('[AI 思考') || logStr.includes('[AI 思考结论]');
                        return (
                          <div 
                            key={lIdx} 
                            className={`${isAiThought ? 'text-cyan-300 font-semibold bg-cyan-950/20 py-0.5 px-1.5 rounded border-l-2 border-cyan-400' : 'text-emerald-400'}`}
                          >
                            {logStr}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>

              {/* Row 2: Results Table (Full Width) */}
              <div className="w-full bg-white border border-slate-100 rounded-2xl p-6 shadow-sm flex flex-col gap-4">
                <div className="flex justify-between items-center pb-2 border-b border-slate-100">
                  <div>
                    <h3 className="font-bold text-slate-900 text-base">搜集到的群组库</h3>
                    <p className="text-xs text-slate-400 mt-0.5">查看 AI 分析过的群组质量，勾选一键导入您的加群任务中。</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={fetchScrapedGroups}
                      className="p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-50 rounded-xl transition-all border border-slate-100 flex items-center justify-center"
                      title="刷新列表"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Filters & Actions Panel */}
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-1.5 text-xs text-slate-500 bg-slate-50 border border-slate-100 rounded-xl px-3 py-1.5">
                    <span>AI 分类:</span>
                    <select
                      value={scrapedFilterCategory}
                      onChange={(e) => setScrapedFilterCategory(e.target.value)}
                      className="bg-transparent font-semibold focus:outline-none cursor-pointer"
                    >
                      <option value="all">全部</option>
                      <option value="life">生活聊天群</option>
                      <option value="business">商业广告群</option>
                      <option value="spam">垃圾/死群</option>
                      <option value="unknown">未分类/私有</option>
                    </select>
                  </div>

                  <div className="flex items-center gap-1.5 text-xs text-slate-500 bg-slate-50 border border-slate-100 rounded-xl px-3 py-1.5">
                    <span>评分限额:</span>
                    <select
                      value={scrapedMinScoreFilter}
                      onChange={(e) => setScrapedMinScoreFilter(Number(e.target.value))}
                      className="bg-transparent font-semibold focus:outline-none cursor-pointer"
                    >
                      <option value="0">全部分数</option>
                      <option value="70">≥ 70分 (推荐)</option>
                      <option value="50">≥ 50分 (一般)</option>
                      <option value="30">≥ 30分</option>
                    </select>
                  </div>
                </div>

                {/* Table Data */}
                <div className="border border-slate-100 rounded-xl overflow-hidden overflow-y-auto max-h-[600px] shrink-0">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 font-semibold select-none whitespace-nowrap">
                        <th className="p-4 w-10 text-center">
                          <input
                            type="checkbox"
                            checked={scrapedGroups.length > 0 && selectedScrapedGroupIds.length === scrapedGroups.length}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedScrapedGroupIds(scrapedGroups.map(g => g.id));
                              } else {
                                setSelectedScrapedGroupIds([]);
                              }
                            }}
                            className="w-3.5 h-3.5 rounded border-slate-200 cursor-pointer"
                          />
                        </th>
                        <th className="p-4">群组标题</th>
                        <th 
                          onClick={() => {
                            if (scrapedSortField === 'time') {
                              setScrapedSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
                            } else {
                              setScrapedSortField('time');
                              setScrapedSortOrder('desc');
                            }
                          }}
                          className="p-4 cursor-pointer hover:bg-slate-100/30 select-none whitespace-nowrap"
                        >
                          <div className="flex items-center gap-1">
                            <span>搜集时间</span>
                            {scrapedSortField === 'time' && (scrapedSortOrder === 'asc' ? ' ▲' : ' ▼')}
                          </div>
                        </th>
                        <th 
                          onClick={() => {
                            if (scrapedSortField === 'member_count') {
                              setScrapedSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
                            } else {
                              setScrapedSortField('member_count');
                              setScrapedSortOrder('desc');
                            }
                          }}
                          className="p-4 cursor-pointer hover:bg-slate-100/30 select-none whitespace-nowrap"
                        >
                          <div className="flex items-center gap-1">
                            <span>成员人数</span>
                            {scrapedSortField === 'member_count' && (scrapedSortOrder === 'asc' ? ' ▲' : ' ▼')}
                          </div>
                        </th>
                        <th className="p-4">AI 属性分类</th>
                        <th 
                          onClick={() => {
                            if (scrapedSortField === 'quality_score') {
                              setScrapedSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
                            } else {
                              setScrapedSortField('quality_score');
                              setScrapedSortOrder('desc');
                            }
                          }}
                          className="p-4 cursor-pointer hover:bg-slate-100/30 select-none whitespace-nowrap"
                        >
                          <div className="flex items-center gap-1">
                            <span>AI 质量评分</span>
                            {scrapedSortField === 'quality_score' && (scrapedSortOrder === 'asc' ? ' ▲' : ' ▼')}
                          </div>
                        </th>
                        <th 
                          onClick={() => {
                            if (scrapedSortField === 'status') {
                              setScrapedSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
                            } else {
                              setScrapedSortField('status');
                              setScrapedSortOrder('desc');
                            }
                          }}
                          className="p-4 cursor-pointer hover:bg-slate-100/30 select-none whitespace-nowrap"
                        >
                          <div className="flex items-center gap-1">
                            <span>加入状态</span>
                            {scrapedSortField === 'status' && (scrapedSortOrder === 'asc' ? ' ▲' : ' ▼')}
                          </div>
                        </th>
                        <th className="p-4 w-20 text-center">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {scrapedGroups.length === 0 ? (
                        <tr>
                          <td colSpan={8} className="p-10 text-center text-slate-400 font-light">
                            没有搜集到符合过滤条件的群组。请在上方新建搜寻任务开始。
                          </td>
                        </tr>
                      ) : (
                        [...scrapedGroups]
                          .sort((a, b) => {
                            const aIgnored = a.status === 'ignored';
                            const bIgnored = b.status === 'ignored';
                            if (aIgnored && !bIgnored) return 1;
                            if (!aIgnored && bIgnored) return -1;
                            
                            let valA: any;
                            let valB: any;
                            if (scrapedSortField === 'time') {
                              valA = a.created_at ? new Date(a.created_at).getTime() : 0;
                              valB = b.created_at ? new Date(b.created_at).getTime() : 0;
                            } else if (scrapedSortField === 'member_count') {
                              valA = a.member_count || 0;
                              valB = b.member_count || 0;
                            } else if (scrapedSortField === 'quality_score') {
                              valA = a.quality_score || 0;
                              valB = b.quality_score || 0;
                            } else if (scrapedSortField === 'status') {
                              valA = a.status || '';
                              valB = b.status || '';
                            }
                            
                            if (valA < valB) return scrapedSortOrder === 'asc' ? -1 : 1;
                            if (valA > valB) return scrapedSortOrder === 'asc' ? 1 : -1;
                            return 0;
                          })
                          .map((g) => {
                            const isSelected = selectedScrapedGroupIds.includes(g.id);
                            const isIgnored = g.status === 'ignored';
                            return (
                              <tr 
                                key={g.id} 
                                className={`hover:bg-slate-50/50 transition-colors cursor-pointer ${isSelected ? 'bg-blue-50/10' : ''} ${isIgnored ? 'opacity-60' : ''}`}
                                onClick={(e) => {
                                  if ((e.target as HTMLElement).closest('input') || (e.target as HTMLElement).closest('a') || (e.target as HTMLElement).closest('button')) {
                                    return;
                                  }
                                  setSelectedScrapedGroupDetail(g);
                                }}
                              >
                                <td className="p-4 text-center">
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={(e) => {
                                      if (e.target.checked) {
                                        setSelectedScrapedGroupIds(prev => [...prev, g.id]);
                                      } else {
                                        setSelectedScrapedGroupIds(prev => prev.filter(id => id !== g.id));
                                      }
                                    }}
                                    className="w-3.5 h-3.5 rounded border-slate-200 cursor-pointer"
                                  />
                                </td>
                                <td className="p-4 font-semibold text-slate-800">
                                  <div className="flex flex-col gap-0.5">
                                    <span>{g.title || g.id}</span>
                                    <a href={g.link} target="_blank" rel="noopener noreferrer" className="text-[10px] text-blue-500 hover:underline flex items-center gap-0.5">
                                      @{g.id}
                                      <ExternalLink className="w-2.5 h-2.5" />
                                    </a>
                                  </div>
                                </td>
                                <td className="p-4 text-slate-500 font-mono text-[11px] whitespace-nowrap">
                                  {formatTime(g.created_at)}
                                </td>
                                <td className="p-4 font-mono font-medium text-slate-600 whitespace-nowrap">
                                  {g.member_count > 0 ? g.member_count.toLocaleString() : '私有群 / 暂无'}
                                </td>
                                <td className="p-4 whitespace-nowrap">
                                  {g.category === 'life' && (
                                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-100 whitespace-nowrap">
                                      🇮🇳 生活聊天
                                    </span>
                                  )}
                                  {g.category === 'business' && (
                                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-purple-50 text-purple-600 border border-purple-100 whitespace-nowrap">
                                      📢 广告同行
                                    </span>
                                  )}
                                  {g.category === 'spam' && (
                                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-slate-100 text-slate-500 whitespace-nowrap">
                                      🗑️ 垃圾/灌水
                                    </span>
                                  )}
                                  {g.category === 'unknown' && (
                                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-slate-50 text-slate-400 whitespace-nowrap">
                                      待测/私有
                                    </span>
                                  )}
                                </td>
                                <td className="p-4 whitespace-nowrap">
                                  <div className="flex items-center gap-2">
                                    <div className="w-16 bg-slate-100 rounded-full h-2 overflow-hidden shrink-0">
                                      <div 
                                        className={`h-full rounded-full ${g.quality_score >= 70 ? 'bg-emerald-500' : g.quality_score >= 40 ? 'bg-amber-400' : 'bg-rose-500'}`}
                                        style={{ width: `${g.quality_score}%` }}
                                      ></div>
                                    </div>
                                    <span className="font-bold font-mono text-slate-700">{g.quality_score}</span>
                                  </div>
                                </td>
                                <td className="p-4 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                                  {g.status === 'joined' ? (
                                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-600 whitespace-nowrap">已导入</span>
                                  ) : g.status === 'ignored' ? (
                                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-400 whitespace-nowrap">已忽略</span>
                                  ) : (
                                    <button
                                      onClick={() => {
                                        setGroupToImportCategory(g);
                                      }}
                                      className="px-2.5 py-1 bg-amber-500 hover:bg-amber-600 active:scale-95 text-white rounded text-[10px] font-bold transition-all shadow-sm flex items-center justify-center gap-1 cursor-pointer"
                                    >
                                      保存群组
                                    </button>
                                  )}
                                </td>
                                <td className="p-4 text-center whitespace-nowrap">
                                  <div className="flex items-center justify-center gap-2">
                                    {g.status !== 'ignored' ? (
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          ignoreSingleScraped(g.id);
                                        }}
                                        className="text-xs text-slate-500 hover:text-rose-600 hover:underline font-semibold whitespace-nowrap"
                                      >
                                        忽略
                                      </button>
                                    ) : (
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          activateSingleScraped(g.id);
                                        }}
                                        className="text-xs text-emerald-500 hover:text-emerald-700 hover:underline font-semibold whitespace-nowrap"
                                      >
                                        激活
                                      </button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            );
                          })
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Batch Actions footer bar */}
                {selectedScrapedGroupIds.length > 0 && (
                  <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-3 flex justify-between items-center gap-3 animate-fade-in shrink-0">
                    <span className="text-xs text-blue-700 font-medium">
                      已选中 <strong className="text-blue-900 font-bold">{selectedScrapedGroupIds.length}</strong> 个搜集到的群组
                    </span>
                    <div className="flex flex-wrap items-center gap-3 text-xs">
                      <div className="flex items-center gap-1.5 text-xs text-slate-500 bg-white border border-slate-100 rounded-xl px-3 py-1.5 shadow-sm">
                        <span>导入加群并归类为:</span>
                        <select
                          value={categoryToAssignScraped}
                          onChange={(e) => setCategoryToAssignScraped(e.target.value)}
                          className="bg-transparent font-semibold focus:outline-none cursor-pointer text-slate-700"
                        >
                          {groupCategories.map((c) => (
                            <option key={c.name} value={c.name}>{c.name}</option>
                          ))}
                        </select>
                      </div>
                      
                      <button
                        onClick={() => handleBatchActionScraped('join')}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white rounded-xl font-bold text-xs shadow-sm transition-all flex items-center gap-1"
                      >
                        <PlusCircle className="w-3.5 h-3.5" />
                        批量导入加群任务
                      </button>

                      <button
                        onClick={() => handleBatchActionScraped('ignore')}
                        className="px-4 py-2 bg-slate-200 hover:bg-slate-300 active:scale-95 text-slate-700 rounded-xl font-bold text-xs transition-all"
                      >
                        忽略
                      </button>

                      <button
                        onClick={() => handleBatchActionScraped('delete')}
                        className="px-4 py-2 bg-rose-50 hover:bg-rose-100 active:scale-95 text-rose-600 rounded-xl font-bold text-xs transition-all border border-rose-100"
                      >
                        批量删除
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Scraped Group Detail Modal Popup */}
              {selectedScrapedGroupDetail && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
                  <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col max-h-[85vh] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                    {/* Header */}
                    <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                      <div>
                        <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
                          <Compass className="w-4 h-4 text-blue-500" />
                          群组评估详情
                        </h3>
                        <p className="text-[10px] text-slate-400 mt-0.5 font-light">由 AI 智能评估分析得出</p>
                      </div>
                      <button 
                        onClick={() => setSelectedScrapedGroupDetail(null)}
                        className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"
                      >
                        <span className="text-lg">✕</span>
                      </button>
                    </div>

                    {/* Body */}
                    <div className="p-5 overflow-y-auto flex flex-col gap-4 text-xs">
                      {/* Group Title and Link */}
                      <div className="flex flex-col gap-1 bg-slate-50 border border-slate-100 rounded-xl p-3">
                        <span className="text-[10px] text-slate-400 font-bold uppercase">群组标题</span>
                        <div className="font-bold text-slate-900 text-sm">{selectedScrapedGroupDetail.title || selectedScrapedGroupDetail.id}</div>
                        <div className="flex items-center gap-3 mt-1 text-[11px]">
                          <a 
                            href={selectedScrapedGroupDetail.link} 
                            target="_blank" 
                            rel="noreferrer" 
                            className="text-blue-500 hover:underline flex items-center gap-0.5"
                          >
                            @{selectedScrapedGroupDetail.id}
                            <ExternalLink className="w-3 h-3" />
                          </a>
                          <span className="text-slate-300">|</span>
                          <span className="text-slate-500">{selectedScrapedGroupDetail.member_count > 0 ? selectedScrapedGroupDetail.member_count.toLocaleString() + ' 成员' : '私有群 / 暂无'}</span>
                        </div>
                      </div>

                      {/* Detail Metrics */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="border border-slate-100 rounded-xl p-3 flex flex-col gap-1">
                          <span className="text-[10px] text-slate-400 font-bold uppercase">AI 属性分类</span>
                          <div className="font-bold text-slate-800 text-sm">
                            {selectedScrapedGroupDetail.category === 'life' ? '🇮🇳 生活聊天群' : selectedScrapedGroupDetail.category === 'business' ? '📢 商业广告同行群' : selectedScrapedGroupDetail.category === 'spam' ? '🗑️ 灌水/无价值群' : '待定/私有'}
                          </div>
                        </div>
                        <div className="border border-slate-100 rounded-xl p-3 flex flex-col gap-1">
                          <span className="text-[10px] text-slate-400 font-bold uppercase">AI 质量评分</span>
                          <div className={`font-bold text-sm ${selectedScrapedGroupDetail.quality_score >= 70 ? 'text-emerald-600' : selectedScrapedGroupDetail.quality_score >= 40 ? 'text-amber-500' : 'text-rose-500'}`}>
                            {selectedScrapedGroupDetail.quality_score} 分
                          </div>
                        </div>
                      </div>

                      {/* AI Reasoning Analysis */}
                      <div className="border border-slate-100 rounded-xl p-3 flex flex-col gap-1">
                        <span className="text-[10px] text-slate-400 font-bold uppercase mb-1">AI 评估依据结论</span>
                        <p className="text-slate-600 leading-relaxed font-light">{selectedScrapedGroupDetail.reason || '暂无详细评估说明。'}</p>
                      </div>
                    </div>

                    {/* Footer */}
                    <div className="p-5 border-t border-slate-100 flex justify-between bg-slate-50/35">
                      {selectedScrapedGroupDetail.status !== 'ignored' ? (
                        <button
                          onClick={() => {
                            ignoreSingleScraped(selectedScrapedGroupDetail.id);
                            setSelectedScrapedGroupDetail(null);
                          }}
                          className="px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-600 font-bold rounded-lg text-xs transition-colors border border-rose-100"
                        >
                          忽略
                        </button>
                      ) : (
                        <button
                          onClick={() => {
                            activateSingleScraped(selectedScrapedGroupDetail.id);
                            setSelectedScrapedGroupDetail(null);
                          }}
                          className="px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-lg text-xs transition-colors"
                        >
                          激活
                        </button>
                      )}
                      <div className="flex gap-2">
                        <button
                          onClick={() => setSelectedScrapedGroupDetail(null)}
                          className="px-3 py-1.5 border border-slate-200 hover:bg-slate-50 text-slate-600 font-bold rounded-lg text-xs transition-colors"
                        >
                          关闭
                        </button>
                        {selectedScrapedGroupDetail.status !== 'joined' ? (
                          <button
                            onClick={() => {
                              setGroupToImportCategory(selectedScrapedGroupDetail);
                              setSelectedScrapedGroupDetail(null);
                            }}
                            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg text-xs transition-colors"
                          >
                            保存群组
                          </button>
                        ) : (
                          <span className="px-3 py-1.5 text-blue-600 font-bold text-xs flex items-center">已导入</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'expansion' && (
            <div className="flex flex-col gap-6 w-full animate-fade-in">
              {/* Row 1: Config (Left) & Real-time Logs (Right) */}
              <div className="flex flex-col lg:flex-row gap-6 items-stretch w-full">
                {/* Left Panel: Autonomous controls */}
                <div className="w-full lg:w-[450px] bg-white border border-slate-100 rounded-2xl p-6 shadow-sm flex flex-col gap-5 shrink-0">
                  <div>
                    <h3 className="font-bold text-slate-900 text-base flex items-center gap-1.5">
                      <Compass className="w-4 h-4 text-blue-500" />
                      自主业务拓展 Agent
                    </h3>
                    <p className="text-xs text-slate-400 mt-1">AI 自主设定关键词并在后台循环搜群与智能质量打分。</p>
                  </div>

                  {/* Status Indicator */}
                  <div className="bg-slate-50 border border-slate-100 rounded-xl p-4 flex flex-col gap-2">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-500 font-medium">任务状态</span>
                      <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                        expansionStatus === 'running' 
                          ? 'bg-emerald-50 text-emerald-600 animate-pulse' 
                          : expansionStatus === 'paused' 
                          ? 'bg-amber-50 text-amber-600' 
                          : 'bg-slate-100 text-slate-500'
                      }`}>
                        {expansionStatus === 'running' ? '运行中' : expansionStatus === 'paused' ? '已暂停' : '已停止'}
                      </span>
                    </div>
                    {expansionKeyword && (
                      <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-1">
                        <span className="text-slate-400">当前搜索关键词:</span>
                        <span className="font-bold text-blue-600 bg-blue-50/50 px-1.5 py-0.5 rounded">
                          {expansionKeyword}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Config Form - Collapsible */}
                  {expansionStatus !== 'running' ? (
                    <div className="flex flex-col gap-3 animate-fade-in">
                      <label className="text-xs font-bold text-slate-700">拓展业务目标设定</label>
                      <textarea
                        value={expansionTarget}
                        onChange={(e) => setExpansionTarget(e.target.value)}
                        placeholder="在此输入您的业务方向（例如印度的生活聊天群，同行USDT承兑群等）..."
                        rows={4}
                        className="w-full border border-slate-200 rounded-xl p-3 text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                        disabled={expansionStatus === 'running'}
                      />
                      <div className="flex items-center justify-between text-xs mt-1">
                        <span className="text-slate-500">搜索循环间隔 (分钟)</span>
                        <select
                          value={expansionInterval}
                          onChange={(e) => setExpansionInterval(parseInt(e.target.value))}
                          className="border border-slate-200 rounded-lg px-2 py-1 focus:outline-none text-xs"
                          disabled={expansionStatus === 'running'}
                        >
                          <option value={5}>5 分钟</option>
                          <option value={10}>10 分钟</option>
                          <option value={15}>15 分钟 (推荐)</option>
                          <option value={30}>30 分钟</option>
                          <option value={60}>60 分钟</option>
                        </select>
                      </div>

                      {/* Auto-Join Control */}
                      <div className="border-t border-slate-100 pt-3 flex flex-col gap-3">
                        <div className="flex justify-between items-center">
                          <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                            <Users className="w-3.5 h-3.5 text-blue-500" />
                            自动加群控制
                          </span>
                          <label className="relative inline-flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              checked={expansionAutoJoin}
                              onChange={(e) => setExpansionAutoJoin(e.target.checked)}
                              disabled={expansionStatus === 'running'}
                              className="sr-only peer"
                            />
                            <div className="w-8 h-4 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3 after:w-3.5 after:transition-all peer-checked:bg-blue-600"></div>
                          </label>
                        </div>

                        {expansionAutoJoin && (
                          <div className="flex flex-col gap-3 pt-2 border-t border-slate-200/60 animate-fade-in">
                            <div className="flex flex-col gap-1.5">
                              <div className="flex justify-between items-center">
                                <label className="text-[11px] font-semibold text-slate-500">加群最低分门槛</label>
                                <span className="text-[11px] font-bold text-blue-600">{expansionAutoJoinMinScore} 分</span>
                              </div>
                              <input
                                type="range"
                                min="10"
                                max="100"
                                step="5"
                                value={expansionAutoJoinMinScore}
                                onChange={(e) => setExpansionAutoJoinMinScore(Number(e.target.value))}
                                disabled={expansionStatus === 'running'}
                                className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                              />
                            </div>

                            <div className="grid grid-cols-3 gap-2">
                              <div className="flex flex-col gap-1">
                                <label className="text-[10px] font-semibold text-slate-400">单轮限制 (个)</label>
                                <input
                                  type="number"
                                  min="1"
                                  value={expansionGroupsPerRound}
                                  onChange={(e) => setExpansionGroupsPerRound(Number(e.target.value))}
                                  disabled={expansionStatus === 'running'}
                                  className="w-full border border-slate-200 rounded-lg px-2 py-1 text-[11px] focus:ring-1 focus:ring-blue-500 focus:outline-none bg-white"
                                />
                              </div>
                              <div className="flex flex-col gap-1">
                                <label className="text-[10px] font-semibold text-slate-400">轮次间隔 (分)</label>
                                <input
                                  type="number"
                                  min="1"
                                  value={expansionRoundInterval}
                                  onChange={(e) => setExpansionRoundInterval(Number(e.target.value))}
                                  disabled={expansionStatus === 'running'}
                                  className="w-full border border-slate-200 rounded-lg px-2 py-1 text-[11px] focus:ring-1 focus:ring-blue-500 focus:outline-none bg-white"
                                />
                              </div>
                              <div className="flex flex-col gap-1">
                                <label className="text-[10px] font-semibold text-slate-400">最大限制 (轮)</label>
                                <input
                                  type="text"
                                  value={expansionMaxRounds}
                                  onChange={(e) => {
                                    const val = e.target.value;
                                    setExpansionMaxRounds(val === '' ? '' : (parseInt(val) || ''));
                                  }}
                                  placeholder="无限制"
                                  disabled={expansionStatus === 'running'}
                                  className="w-full border border-slate-200 rounded-lg px-2 py-1 text-[11px] focus:ring-1 focus:ring-blue-500 focus:outline-none bg-white"
                                />
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 text-xs text-slate-600 flex flex-col gap-1.5 animate-fade-in">
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-slate-700">当前拓展目标</span>
                        <button 
                          onClick={() => pauseExpansion()}
                          className="text-[10px] text-blue-500 hover:underline font-semibold"
                        >
                          点击修改
                        </button>
                      </div>
                      <p className="text-[11px] text-slate-500 line-clamp-2 italic">"{expansionTarget}"</p>
                      <div className="text-[10px] text-slate-400 mt-0.5 flex flex-col gap-0.5">
                       <span>循环间隔: {expansionInterval} 分钟</span>
                       <span>自动加群: {expansionAutoJoin ? `启用 (门槛: ${expansionAutoJoinMinScore}分, ${expansionGroupsPerRound}个/轮, 间隔: ${expansionRoundInterval}分)` : '禁用'}</span>
                     </div>
                    </div>
                  )}

                  {/* Controls */}
                  <div className="flex gap-3 mt-1">
                    {expansionStatus === 'running' ? (
                      <button
                        onClick={pauseExpansion}
                        className="flex-1 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-xs font-bold transition-all shadow-sm shadow-amber-500/10 flex items-center justify-center gap-1.5"
                      >
                        <Pause className="w-3.5 h-3.5" />
                        暂停业务拓展
                      </button>
                    ) : (
                      <button
                        onClick={startExpansion}
                        className="flex-1 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm shadow-blue-600/10 flex items-center justify-center gap-1.5"
                      >
                        <Play className="w-3.5 h-3.5" />
                        {expansionStatus === 'paused' ? '恢复运行' : '开启自主搜群'}
                      </button>
                    )}
                  </div>
                </div>

                {/* Right Panel: Real-time Logs Console */}
                <div className="flex-1 bg-white border border-slate-100 rounded-2xl p-6 shadow-sm flex flex-col gap-3 min-h-[350px]">
                  <div>
                    <h3 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                      <FileText className="w-4 h-4 text-blue-500" />
                      AI 思考与运行日志
                    </h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">实时展示 Agent 搜群状态、AI 评分打分等思考过程。</p>
                  </div>
                  <div ref={scrapedLogsContainerRef} className="flex-1 bg-slate-900 border border-slate-900 rounded-2xl p-4 font-mono text-[10px] text-emerald-400 overflow-y-auto flex flex-col gap-1.5 leading-relaxed shadow-inner min-h-[250px]">
                    {expansionLogs.length === 0 ? (
                      <div className="text-slate-500 text-center py-20">等待 Agent 任务启动输出日志...</div>
                    ) : (
                      expansionLogs.map((logStr, lIdx) => {
                        let isAiThought = logStr.includes('[AI 思考') || logStr.includes('[AI 思考结论]');
                        return (
                          <div 
                            key={lIdx} 
                            className={`${isAiThought ? 'text-cyan-300 font-semibold bg-cyan-950/20 py-0.5 px-1.5 rounded border-l-2 border-cyan-400' : 'text-emerald-400'}`}
                          >
                            {logStr}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>

              {/* Row 2: Display suitable groups found (Full Width) */}
              <div className="w-full bg-white border border-slate-100 rounded-2xl p-6 shadow-sm flex flex-col gap-4">
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="font-bold text-slate-900 text-sm">匹配的高质量群组</h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">展示 AI 判定的生活聊天群及同行专业群组（评分 &gt;= 40）。</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={fetchExpansionGroups}
                      className="p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-50 rounded-xl transition-all border border-slate-100 flex items-center justify-center"
                      title="刷新列表"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Batch Actions panel */}
                {selectedExpansionGroupIds.length > 0 && (
                  <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-3 flex justify-between items-center gap-3 animate-fade-in shrink-0">
                    <span className="text-xs text-blue-700 font-medium">
                      已选中 <strong className="text-blue-900 font-bold">{selectedExpansionGroupIds.length}</strong> 个群组
                    </span>
                    <div className="flex gap-2 text-xs">
                      <button
                        onClick={() => batchActionExpansionGroups('join', selectedExpansionGroupIds)}
                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg"
                      >
                        批量加入加群库
                      </button>
                      <button
                        onClick={() => batchActionExpansionGroups('ignore', selectedExpansionGroupIds)}
                        className="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold rounded-lg"
                      >
                        忽略选中
                      </button>
                    </div>
                  </div>
                )}

                {/* Groups Library Table */}
                <div className="border border-slate-100 rounded-xl overflow-hidden overflow-y-auto max-h-[600px] shrink-0">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 font-semibold select-none whitespace-nowrap">
                        <th className="p-4 w-10 text-center">
                          <input
                            type="checkbox"
                            checked={expansionGroups.length > 0 && selectedExpansionGroupIds.length === expansionGroups.length}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedExpansionGroupIds(expansionGroups.map(g => g.id));
                              } else {
                                setSelectedExpansionGroupIds([]);
                              }
                            }}
                            className="w-3.5 h-3.5 rounded border-slate-200 cursor-pointer"
                          />
                        </th>
                        <th className="p-4">群组标题</th>
                        <th 
                          onClick={() => {
                            if (expansionSortField === 'time') {
                              setExpansionSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
                            } else {
                              setExpansionSortField('time');
                              setExpansionSortOrder('desc');
                            }
                          }}
                          className="p-4 cursor-pointer hover:bg-slate-100/30 select-none whitespace-nowrap"
                        >
                          <div className="flex items-center gap-1">
                            <span>发现时间</span>
                            {expansionSortField === 'time' && (expansionSortOrder === 'asc' ? ' ▲' : ' ▼')}
                          </div>
                        </th>
                        <th 
                          onClick={() => {
                            if (expansionSortField === 'member_count') {
                              setExpansionSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
                            } else {
                              setExpansionSortField('member_count');
                              setExpansionSortOrder('desc');
                            }
                          }}
                          className="p-4 cursor-pointer hover:bg-slate-100/30 select-none whitespace-nowrap"
                        >
                          <div className="flex items-center gap-1">
                            <span>成员人数</span>
                            {expansionSortField === 'member_count' && (expansionSortOrder === 'asc' ? ' ▲' : ' ▼')}
                          </div>
                        </th>
                        <th className="p-4">AI 属性分类</th>
                        <th 
                          onClick={() => {
                            if (expansionSortField === 'quality_score') {
                              setExpansionSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
                            } else {
                              setExpansionSortField('quality_score');
                              setExpansionSortOrder('desc');
                            }
                          }}
                          className="p-4 cursor-pointer hover:bg-slate-100/30 select-none whitespace-nowrap"
                        >
                          <div className="flex items-center gap-1">
                            <span>AI 质量评分</span>
                            {expansionSortField === 'quality_score' && (expansionSortOrder === 'asc' ? ' ▲' : ' ▼')}
                          </div>
                        </th>
                        <th className="p-4 whitespace-nowrap">加入状态</th>
                        <th className="p-4 w-20 text-center">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {expansionGroups.length === 0 ? (
                        <tr>
                          <td colSpan={8} className="p-10 text-center text-slate-400 font-light">
                            暂无由业务拓展 Agent 搜寻到的高质量群组。开启左侧 Agent 后自动收集。
                          </td>
                        </tr>
                      ) : (
                        [...expansionGroups]
                          .sort((a, b) => {
                            const aIgnored = a.status === 'ignored';
                            const bIgnored = b.status === 'ignored';
                            if (aIgnored && !bIgnored) return 1;
                            if (!aIgnored && bIgnored) return -1;
                            
                            let valA: any;
                            let valB: any;
                            if (expansionSortField === 'time') {
                              valA = a.created_at ? new Date(a.created_at).getTime() : 0;
                              valB = b.created_at ? new Date(b.created_at).getTime() : 0;
                            } else if (expansionSortField === 'member_count') {
                              valA = a.member_count || 0;
                              valB = b.member_count || 0;
                            } else if (expansionSortField === 'quality_score') {
                              valA = a.quality_score || 0;
                              valB = b.quality_score || 0;
                            }
                            
                            if (valA < valB) return expansionSortOrder === 'asc' ? -1 : 1;
                            if (valA > valB) return expansionSortOrder === 'asc' ? 1 : -1;
                            return 0;
                          })
                          .map((g) => {
                            const isSelected = selectedExpansionGroupIds.includes(g.id);
                            const isIgnored = g.status === 'ignored';
                            return (
                              <tr 
                                key={g.id} 
                                className={`hover:bg-slate-50/50 transition-colors cursor-pointer ${isSelected ? 'bg-blue-50/10' : ''} ${isIgnored ? 'opacity-60' : ''}`}
                                onClick={(e) => {
                                  if ((e.target as HTMLElement).closest('input') || (e.target as HTMLElement).closest('a') || (e.target as HTMLElement).closest('button')) {
                                    return;
                                  }
                                  setSelectedExpansionGroupDetail(g);
                                }}
                              >
                                <td className="p-4 text-center">
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={(e) => {
                                      if (e.target.checked) {
                                        setSelectedExpansionGroupIds(prev => [...prev, g.id]);
                                      } else {
                                        setSelectedExpansionGroupIds(prev => prev.filter(id => id !== g.id));
                                      }
                                    }}
                                    className="w-3.5 h-3.5 rounded border-slate-200 cursor-pointer"
                                  />
                                </td>
                                <td className="p-4 font-semibold text-slate-800">
                                  <div className="flex flex-col gap-0.5">
                                    <span>{g.title || g.id}</span>
                                    <a href={g.link} target="_blank" rel="noopener noreferrer" className="text-[10px] text-blue-500 hover:underline flex items-center gap-0.5">
                                      @{g.id}
                                      <ExternalLink className="w-2.5 h-2.5" />
                                    </a>
                                  </div>
                                </td>
                                <td className="p-4 text-slate-500 font-mono text-[11px] whitespace-nowrap">
                                  {formatTime(g.created_at)}
                                </td>
                                <td className="p-4 font-mono font-medium text-slate-600 whitespace-nowrap">
                                  {g.member_count > 0 ? g.member_count.toLocaleString() : '私有群 / 暂无'}
                                </td>
                                <td className="p-4 whitespace-nowrap">
                                  {g.category === 'life' && (
                                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-100 whitespace-nowrap">
                                      🇮🇳 生活聊天
                                    </span>
                                  )}
                                  {g.category === 'business' && (
                                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-purple-50 text-purple-600 border border-purple-100 whitespace-nowrap">
                                      📢 广告同行
                                    </span>
                                  )}
                                  {g.category === 'spam' && (
                                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-slate-100 text-slate-500 whitespace-nowrap">
                                      🗑️ 垃圾/灌水
                                    </span>
                                  )}
                                  {g.category === 'unknown' && (
                                    <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-slate-50 text-slate-400 whitespace-nowrap">
                                      待测/私有
                                    </span>
                                  )}
                                </td>
                                <td className="p-4 whitespace-nowrap">
                                  <div className="flex items-center gap-2">
                                    <div className="w-16 bg-slate-100 rounded-full h-2 overflow-hidden shrink-0">
                                      <div 
                                        className={`h-full rounded-full ${g.quality_score >= 70 ? 'bg-emerald-500' : g.quality_score >= 40 ? 'bg-amber-400' : 'bg-rose-500'}`}
                                        style={{ width: `${g.quality_score}%` }}
                                      ></div>
                                    </div>
                                    <span className="font-bold font-mono text-slate-700">{g.quality_score}</span>
                                  </div>
                                </td>
                                <td className="p-4 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                                  {g.status === 'joined' ? (
                                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-600 whitespace-nowrap">已导入</span>
                                  ) : g.status === 'ignored' ? (
                                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-400 whitespace-nowrap">已忽略</span>
                                  ) : (
                                    <button
                                      onClick={() => {
                                        setGroupToImportCategory(g);
                                      }}
                                      className="px-2.5 py-1 bg-amber-500 hover:bg-amber-600 active:scale-95 text-white rounded text-[10px] font-bold transition-all shadow-sm flex items-center justify-center gap-1 cursor-pointer"
                                    >
                                      保存群组
                                    </button>
                                  )}
                                </td>
                                <td className="p-4 text-center whitespace-nowrap">
                                  <div className="flex items-center justify-center gap-2">
                                    {g.status !== 'ignored' ? (
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          batchActionExpansionGroups('ignore', [g.id]);
                                        }}
                                        className="text-xs text-slate-500 hover:text-rose-600 hover:underline font-semibold whitespace-nowrap"
                                      >
                                        忽略
                                      </button>
                                    ) : (
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          batchActionExpansionGroups('unignore', [g.id]);
                                        }}
                                        className="text-xs text-emerald-500 hover:text-emerald-700 hover:underline font-semibold whitespace-nowrap"
                                      >
                                        激活
                                      </button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            );
                          })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Detail Modal Pop-up */}
              {selectedExpansionGroupDetail && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
                  <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col max-h-[85vh] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                    {/* Header */}
                    <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                      <div>
                        <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
                          <Compass className="w-4 h-4 text-blue-500" />
                          群组评估详情
                        </h3>
                        <p className="text-[10px] text-slate-400 mt-0.5 font-light">由 AI Agent 自主搜寻并多维度分析得出</p>
                      </div>
                      <button 
                        onClick={() => setSelectedExpansionGroupDetail(null)}
                        className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"
                      >
                        <span className="text-lg">✕</span>
                      </button>
                    </div>

                    {/* Body */}
                    <div className="p-5 overflow-y-auto flex flex-col gap-4 text-xs">
                      {/* Group Title and Link */}
                      <div className="flex flex-col gap-1 bg-slate-50 border border-slate-100 rounded-xl p-3">
                        <span className="text-[10px] text-slate-400 font-bold uppercase">群组标题</span>
                        <div className="font-bold text-slate-900 text-sm">{selectedExpansionGroupDetail.title || selectedExpansionGroupDetail.id}</div>
                        <div className="flex items-center gap-3 mt-1 text-[11px]">
                          <a 
                            href={selectedExpansionGroupDetail.link} 
                            target="_blank" 
                            rel="noreferrer" 
                            className="text-blue-500 hover:underline flex items-center gap-0.5"
                          >
                            @{selectedExpansionGroupDetail.id}
                            <ExternalLink className="w-3 h-3" />
                          </a>
                          <span className="text-slate-300">|</span>
                          <span className="text-slate-500">{selectedExpansionGroupDetail.member_count?.toLocaleString()} 成员</span>
                        </div>
                      </div>

                      {/* Score and Category */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 flex flex-col gap-1">
                          <span className="text-[10px] text-slate-400 font-bold uppercase">AI 质量评分</span>
                          <span className={`text-base font-bold ${
                            selectedExpansionGroupDetail.quality_score >= 80 ? 'text-emerald-600' : selectedExpansionGroupDetail.quality_score >= 50 ? 'text-amber-500' : 'text-rose-500'
                          }`}>
                            {selectedExpansionGroupDetail.quality_score} 分
                          </span>
                          <div className="w-full bg-slate-200 h-1 rounded-full overflow-hidden mt-1">
                            <div 
                              className={`h-full ${
                                selectedExpansionGroupDetail.quality_score >= 80 ? 'bg-emerald-500' : selectedExpansionGroupDetail.quality_score >= 50 ? 'bg-amber-400' : 'bg-rose-400'
                              }`}
                              style={{ width: `${selectedExpansionGroupDetail.quality_score}%` }}
                            />
                          </div>
                        </div>

                        <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 flex flex-col gap-1.5 justify-center">
                          <span className="text-[10px] text-slate-400 font-bold uppercase">AI 属性分类</span>
                          <div>
                            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold inline-block ${
                              selectedExpansionGroupDetail.category === 'life' 
                                ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' 
                                : selectedExpansionGroupDetail.category === 'business' 
                                ? 'bg-purple-50 text-purple-600 border border-purple-100' 
                                : 'bg-slate-50 text-slate-500 border border-slate-100'
                            }`}>
                              {selectedExpansionGroupDetail.category === 'life' ? '印度生活聊天' : selectedExpansionGroupDetail.category === 'business' ? '同行商业广告' : selectedExpansionGroupDetail.category}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Summary */}
                      <div className="flex flex-col gap-1">
                        <span className="text-[10px] font-bold text-slate-400 uppercase">AI 评估与加群分析</span>
                        <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 text-slate-700 leading-relaxed text-[11px]">
                          {selectedExpansionGroupDetail.analysis_summary || '暂无评估摘要'}
                        </div>
                      </div>

                      {/* Keyword */}
                      <div className="flex flex-col gap-1">
                        <span className="text-[10px] font-bold text-slate-400 uppercase">搜索关键词来源</span>
                        <div className="text-[11px] text-slate-600">
                          由 AI 构思关键词 <strong className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-800 font-mono font-bold">{selectedExpansionGroupDetail.keyword}</strong> 搜索并分析得到。
                        </div>
                      </div>
                    </div>

                    {/* Footer */}
                    <div className="p-4 border-t border-slate-100 flex justify-between bg-slate-50/50">
                      {selectedExpansionGroupDetail.status !== 'ignored' ? (
                        <button
                          onClick={() => {
                            batchActionExpansionGroups('ignore', [selectedExpansionGroupDetail.id]);
                            setSelectedExpansionGroupDetail(null);
                          }}
                          className="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold rounded-lg text-xs transition-colors"
                        >
                          忽略
                        </button>
                      ) : (
                        <button
                          onClick={() => {
                            batchActionExpansionGroups('unignore', [selectedExpansionGroupDetail.id]);
                            setSelectedExpansionGroupDetail(null);
                          }}
                          className="px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-lg text-xs transition-colors"
                        >
                          激活
                        </button>
                      )}
                      <div className="flex gap-2">
                        <button
                          onClick={() => setSelectedExpansionGroupDetail(null)}
                          className="px-3 py-1.5 border border-slate-200 hover:bg-slate-50 text-slate-600 font-bold rounded-lg text-xs transition-colors"
                        >
                          关闭
                        </button>
                        <button
                          onClick={() => {
                            setGroupToImportCategory(selectedExpansionGroupDetail);
                            setSelectedExpansionGroupDetail(null);
                          }}
                          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg text-xs transition-colors"
                        >
                          保存群组
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

            </div>
          )}

        {/* Group Import Category Selection Modal Popup */}
        {groupToImportCategory && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-sm flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200" onClick={(e) => e.stopPropagation()}>
              {/* Header */}
              <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                <h3 className="font-bold text-slate-900 text-sm">选择导入分组</h3>
                <button 
                  onClick={() => setGroupToImportCategory(null)}
                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors text-lg"
                >
                  ✕
                </button>
              </div>
              
              {/* Body */}
              <div className="p-5 flex flex-col gap-4 text-xs">
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-500 font-semibold">群组标题/ID：</label>
                  <div className="font-bold text-slate-800 bg-slate-50 p-2.5 rounded-lg border border-slate-100 select-all font-mono break-all">
                    {groupToImportCategory.title || groupToImportCategory.id} (@{groupToImportCategory.id})
                  </div>
                </div>
                
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-500 font-semibold">导入加群并归类为：</label>
                  <select
                    value={selectedImportCategory}
                    onChange={(e) => setSelectedImportCategory(e.target.value)}
                    className="w-full border border-slate-200 rounded-xl p-2.5 bg-slate-50 focus:outline-none focus:bg-white text-slate-700 font-semibold cursor-pointer"
                  >
                    <option value="中文广告">中文广告</option>
                    <option value="英文广告">英文广告</option>
                    <option value="印度生活">印度生活</option>
                  </select>
                </div>
              </div>
              
              {/* Footer */}
              <div className="p-4 border-t border-slate-100 flex justify-end gap-2 bg-slate-50/50">
                <button
                  onClick={() => setGroupToImportCategory(null)}
                  className="px-4 py-2 border border-slate-200 hover:bg-slate-50 text-slate-600 font-bold rounded-lg text-xs transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={() => {
                    singleJoinScraped(groupToImportCategory.id, selectedImportCategory);
                    setGroupToImportCategory(null);
                  }}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg text-xs transition-colors"
                >
                  确认导入
                </button>
              </div>
            </div>
          </div>
        )}


        </div>


        {/* C. BOTTOM RIGHT STICKY TOAST NOTIFICATION PILL */}

        {toastText && (

          <div className="absolute bottom-6 right-6 bg-slate-900 text-white px-5 py-3 rounded-full text-xs font-semibold shadow-lg shadow-black/35 z-40 animate-bounce transition-all flex items-center gap-2">

            <Shield className="w-4 h-4 text-blue-400 shrink-0" />

            <span>{toastText}</span>

          </div>

        )}



        {/* E. BATCH MODIFY ACCOUNTS PROFILE MODAL */}

        {showBatchProfileModal && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col max-h-[85vh] overflow-hidden">

              

              {/* Modal Header */}

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">批量修改个人信息</h3>

                  <p className="text-xs text-slate-400 mt-0.5 font-light">已选择 {selectedAccountIds.length} 个账号</p>

                </div>

                <button 

                  onClick={() => setShowBatchProfileModal(false)}

                  disabled={updatingBatchProfiles}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              {/* Modal Body */}

              <div className="p-6 overflow-y-auto flex flex-col gap-5">

                

                {/* 1. Last name (固定姓氏) */}

                <div className="flex flex-col gap-1.5">

                  <label className="text-xs text-slate-600 font-semibold">固定姓氏 (Last Name)</label>

                  <input 

                    type="text" 

                    value={batchProfileLastName}

                    onChange={(e) => setBatchProfileLastName(e.target.value)}

                    placeholder="例如: rosepay"

                    className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                    disabled={updatingBatchProfiles}

                  />

                  <p className="text-[10px] text-slate-400 leading-normal">

                    设置电报账户的姓氏 (Last Name)。为了规整管理，所有选中账号都会采用此姓氏。

                  </p>

                </div>



                {/* 2. Virtual modify option (是否启用虚拟修改) */}

                <div className="flex items-center gap-2 bg-slate-50 p-3 rounded-lg border border-slate-100">

                  <input 

                    type="checkbox" 

                    id="batchProfileVirtualModify"

                    checked={batchProfileVirtualModify}

                    onChange={(e) => setBatchProfileVirtualModify(e.target.checked)}

                    className="rounded text-blue-600 focus:ring-blue-500/20 border-slate-300 cursor-pointer"

                    disabled={updatingBatchProfiles}

                  />

                  <label htmlFor="batchProfileVirtualModify" className="text-xs text-slate-700 font-semibold cursor-pointer select-none">

                    启用虚拟随机修改 (推荐)

                  </label>

                </div>



                {/* Conditional Fields based on virtual modification */}

                {batchProfileVirtualModify ? (

                  <div className="p-3 bg-blue-50/30 border border-blue-100 rounded-lg text-xs text-blue-800 flex flex-col gap-1.5">

                    <div className="font-semibold">💡 虚拟修改规则：</div>

                    <div className="text-[11px] leading-relaxed">

                      名字从明星/历史人物库 (如：李世民、刘德华、诸葛亮) 中随机分配。

                    </div>

                    <div className="text-[11px] leading-relaxed">

                      Username 会根据姓氏拼音与名拼音组合 (例如 姓 <b>{batchProfileLastName || 'rosepay'}</b>，名 <b>李世民</b> ➔ username: <b>{batchProfileLastName || 'rosepay'}_lishimin</b>)。

                    </div>

                  </div>

                ) : (

                  <div className="flex flex-col gap-4 border border-slate-100 p-4 rounded-xl">

                    <div className="flex flex-col gap-1.5">

                      <label className="text-xs text-slate-600 font-semibold">固定名字 (First Name)</label>

                      <input 

                        type="text" 

                        value={batchProfileFirstName}

                        onChange={(e) => setBatchProfileFirstName(e.target.value)}

                        placeholder="例如: Agent"

                        className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                        disabled={updatingBatchProfiles}

                      />

                    </div>

                    <div className="flex flex-col gap-1.5">

                      <label className="text-xs text-slate-600 font-semibold">Username 前缀 (用户名)</label>

                      <input 

                        type="text" 

                        value={batchProfileUsernamePrefix}

                        onChange={(e) => setBatchProfileUsernamePrefix(e.target.value)}

                        placeholder="例如: rosepay_user"

                        className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                        disabled={updatingBatchProfiles}

                      />

                      <p className="text-[10px] text-slate-400 leading-normal">

                        我们将自动在您的前缀后添加序号 (如 <b>{batchProfileUsernamePrefix || 'prefix'}_1</b>, <b>{batchProfileUsernamePrefix || 'prefix'}_2</b>) 以确保 Telegram 用户名唯一。

                      </p>

                    </div>

                  </div>

                )}



                {/* 3. Unified About/Bio (统一简介) */}

                <div className="flex flex-col gap-1.5 border-t border-slate-100 pt-4">

                  <div className="flex justify-between items-center">

                    <label className="text-xs text-slate-600 font-semibold">统一简介 (Bio, 70字)</label>

                    <span className="text-[10px] text-slate-400 font-mono font-medium">

                      {batchProfileAbout.length} / 70

                    </span>

                  </div>

                  <input 

                    type="text" 

                    value={batchProfileAbout}

                    onChange={(e) => {

                      if (e.target.value.length <= 70) {

                        setBatchProfileAbout(e.target.value);

                      }

                    }}

                    maxLength={70}

                    placeholder="例: 官方客服 / 官方交流群"

                    className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                    disabled={updatingBatchProfiles}

                  />

                  <p className="text-[10px] text-slate-400 leading-normal">

                    批量修改选中电报账号的的个人简介 (Bio)，留空则不修改。

                  </p>

                </div>



              </div>



              {/* Modal Footer */}

              <div className="p-5 border-t border-slate-100 flex justify-end gap-2 bg-slate-50/50">

                <button

                  onClick={() => setShowBatchProfileModal(false)}

                  disabled={updatingBatchProfiles}

                  className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 transition-colors"

                >

                  取消

                </button>

                <button

                  onClick={() => handleBatchUpdateProfiles(true)}

                  disabled={updatingBatchProfiles}

                  className="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white text-xs font-bold rounded-lg shadow-sm transition-all flex items-center gap-1.5"

                >

                  {updatingBatchProfiles ? (

                    <>

                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />

                      <span>正在修改...</span>

                    </>

                  ) : (

                    <span>修改个人简介</span>

                  )}

                </button>

                <button

                  onClick={() => handleBatchUpdateProfiles(false)}

                  disabled={updatingBatchProfiles}

                  className="px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-xs font-bold rounded-lg shadow-sm transition-all flex items-center gap-1.5"

                >

                  {updatingBatchProfiles ? (

                    <>

                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />

                      <span>正在修改...</span>

                    </>

                  ) : (

                    <span>保存并执行</span>

                  )}

                </button>

              </div>



            </div>

          </div>

        )}



        {/* F. BATCH MODIFY ACCOUNTS 2FA MODAL */}

        {showBatch2faModal && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col max-h-[85vh] overflow-hidden">

              

              {/* Modal Header */}

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">批量修改两步验证</h3>

                  <p className="text-xs text-slate-400 mt-0.5 font-light">已选择 {selectedAccountIds.length} 个账号</p>

                </div>

                <button 

                  onClick={() => setShowBatch2faModal(false)}

                  disabled={updatingBatch2fa}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              {/* Modal Body */}

              <div className="p-6 overflow-y-auto flex flex-col gap-5">

                

                {/* 1. Current 2FA Password (current default/likely same) */}

                <div className="flex flex-col gap-1.5">

                  <label className="text-xs text-slate-600 font-semibold">原两步验证密码 (若当前未设置请留空)</label>

                  <input 

                    type="password" 

                    value={batch2faCurrentPassword}

                    onChange={(e) => setBatch2faCurrentPassword(e.target.value)}

                    placeholder="输入当前各账号的2FA密码(大概率相同)"

                    className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500 font-mono"

                    disabled={updatingBatch2fa}

                  />

                </div>



                {/* 2. New Password Mode */}

                <div className="flex flex-col gap-1.5">

                  <label className="text-xs text-slate-600 font-semibold">新密码配置方式</label>

                  <div className="flex gap-2">

                    <button 

                      type="button"

                      onClick={() => setBatch2faNewPasswordMode('same')}

                      className={`flex-grow py-2 border rounded-lg text-xs font-semibold transition-all ${

                        batch2faNewPasswordMode === 'same' 

                          ? 'border-blue-500 bg-blue-50/50 text-blue-600' 

                          : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'

                      }`}

                      disabled={updatingBatch2fa}

                    >

                      统一设定新密码

                    </button>

                    <button 

                      type="button"

                      onClick={() => setBatch2faNewPasswordMode('auto')}

                      className={`flex-grow py-2 border rounded-lg text-xs font-semibold transition-all ${

                        batch2faNewPasswordMode === 'auto' 

                          ? 'border-blue-500 bg-blue-50/50 text-blue-600' 

                          : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'

                      }`}

                      disabled={updatingBatch2fa}

                    >

                      自动生成复杂密码 (推荐)

                    </button>

                  </div>

                </div>



                {/* 3. Conditional New Password Input */}

                {batch2faNewPasswordMode === 'same' ? (

                  <div className="flex flex-col gap-1.5 animate-fade-in">

                    <label className="text-xs text-slate-600 font-semibold">统一新两步验证密码</label>

                    <input 

                      type="text" 

                      value={batch2faCustomNewPassword}

                      onChange={(e) => setBatch2faCustomNewPassword(e.target.value)}

                      placeholder="输入将要设置的新密码"

                      className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500 font-mono"

                      disabled={updatingBatch2fa}

                    />

                  </div>

                ) : (

                  <div className="p-3 bg-blue-50/30 border border-blue-100 rounded-lg text-xs text-blue-800 flex flex-col gap-1.5 animate-fade-in">

                    <div className="font-semibold">💡 自动生成密码规则：</div>

                    <div className="text-[11px] leading-relaxed">

                      系统将为每个账号自动生成 12 位高强度安全密码，并调用电报设置。

                    </div>

                    <div className="text-[11px] leading-relaxed">

                      修改成功后，<b>生成的密码会自动持久化保存到数据库的相应账号中</b>，防止丢失，并弹窗为您列出新密码对照表。

                    </div>

                  </div>

                )}



                {/* 4. Password Hint */}

                <div className="flex flex-col gap-1.5">

                  <label className="text-xs text-slate-600 font-semibold">密码提示信息 (Hint, 可选)</label>

                  <input 

                    type="text" 

                    value={batch2faHint}

                    onChange={(e) => setBatch2faHint(e.target.value)}

                    placeholder="例如: 常用拼音前缀"

                    className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                    disabled={updatingBatch2fa}

                  />

                </div>



              </div>



              {/* Modal Footer */}

              <div className="p-5 border-t border-slate-100 flex justify-end gap-2.5 bg-slate-50/50">

                <button

                  type="button"

                  onClick={() => setShowBatch2faModal(false)}

                  disabled={updatingBatch2fa}

                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 transition-colors"

                >

                  取消

                </button>

                <button

                  type="button"

                  onClick={handleBatchUpdate2fa}

                  disabled={updatingBatch2fa}

                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-xs font-bold rounded-lg shadow-sm transition-all flex items-center gap-1.5"

                >

                  {updatingBatch2fa ? (

                    <>

                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />

                      <span>正在修改并同步...</span>

                    </>

                  ) : (

                    <span>保存并执行</span>

                  )}

                </button>

              </div>



            </div>

          </div>

        )}



        {/* ADD USER MODAL */}

        {showAddUserModal && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col overflow-hidden">

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">添加系统用户</h3>

                  <p className="text-xs text-slate-400 mt-0.5">创建新账户并指定对应的角色</p>

                </div>

                <button 

                  onClick={() => {

                    setShowAddUserModal(false);

                    setNewUserUsername('');

                    setNewUserPassword('');

                    setNewUserTelegramContact('');

                  }}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              <div className="p-6 flex flex-col gap-4">

                <div className="flex flex-col gap-1.5">

                  <label className="text-xs font-semibold text-slate-700">用户名</label>

                  <input 

                    type="text" 

                    value={newUserUsername}

                    onChange={(e) => setNewUserUsername(e.target.value)}

                    placeholder="请输入用户名"

                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-sm focus:outline-none focus:bg-white focus:border-blue-500 font-mono"

                  />

                </div>



                <div className="flex flex-col gap-1.5">

                  <label className="text-xs font-semibold text-slate-700">登录密码</label>

                  <input 

                    type="password" 

                    value={newUserPassword}

                    onChange={(e) => setNewUserPassword(e.target.value)}

                    placeholder="请输入密码（不小于 6 位）"

                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-sm focus:outline-none focus:bg-white focus:border-blue-500"

                  />

                </div>



                <div className="flex flex-col gap-1.5">

                  <label className="text-xs font-semibold text-slate-700">所属公司</label>

                  <select 

                    value={newUserCompany}

                    onChange={(e) => setNewUserCompany(e.target.value)}

                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-sm focus:outline-none focus:bg-white focus:border-blue-500"

                  >

                    <option value="admin">admin</option>

                    {companiesList.filter((c) => c.name !== 'admin').map((c) => (

                      <option key={c.id} value={c.name}>{c.name}</option>

                    ))}

                  </select>

                </div>



                <div className="flex flex-col gap-1.5">

                  <label className="text-xs font-semibold text-slate-700">电报通知账号</label>

                  <input

                    type="text"

                    value={newUserTelegramContact}

                    onChange={(e) => setNewUserTelegramContact(e.target.value)}

                    placeholder="@username 或 t.me/username"

                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-sm focus:outline-none focus:bg-white focus:border-blue-500 font-mono"

                  />

                </div>



                <div className="flex flex-col gap-2">

                  <label className="text-xs font-semibold text-slate-700">角色权限</label>

                  <div className="flex gap-4">

                    <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none font-medium">

                      <input 

                        type="radio" 

                        name="newUserRole" 

                        value="user"

                        checked={newUserRole === 'user'}

                        onChange={() => setNewUserRole('user')}

                        className="text-blue-600 focus:ring-blue-500/20 border-slate-300"

                      />

                      <span>普通操作员</span>

                    </label>

                    <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none font-medium">

                      <input 

                        type="radio" 

                        name="newUserRole" 

                        value="admin"

                        checked={newUserRole === 'admin'}

                        onChange={() => setNewUserRole('admin')}

                        className="text-blue-600 focus:ring-blue-500/20 border-slate-300"

                      />

                      <span>系统管理员</span>

                    </label>

                  </div>

                </div>

              </div>



              <div className="p-5 border-t border-slate-100 flex justify-end gap-2.5 bg-slate-50/35">

                <button 

                  onClick={() => {

                    setShowAddUserModal(false);

                    setNewUserUsername('');

                    setNewUserPassword('');

                    setNewUserTelegramContact('');

                  }}

                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-lg transition-all"

                >

                  取消

                </button>

                <button 

                  onClick={handleCreateUser}

                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-all shadow-sm"

                >

                  确定添加

                </button>

              </div>

            </div>

          </div>

        )}



        {/* EDIT USER MODAL */}

        {showEditUserModal && editUserTarget && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col overflow-hidden">

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">编辑系统用户</h3>

                  <p className="text-xs text-slate-400 mt-0.5">修改用户角色、所属公司或登录密码</p>

                </div>

                <button 

                  onClick={() => {

                    setShowEditUserModal(false);

                    setEditUserTarget(null);

                    setEditUserPassword('');

                    setEditUserTelegramContact('');

                  }}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              <div className="p-6 flex flex-col gap-4">

                <div className="flex flex-col gap-1.5">

                  <label className="text-xs font-semibold text-slate-700">用户名 (不可修改)</label>

                  <input 

                    type="text" 

                    value={editUserTarget.username}

                    disabled

                    className="w-full bg-slate-100 border border-slate-200 rounded-lg p-2.5 text-sm text-slate-500 cursor-not-allowed font-mono"

                  />

                </div>



                <div className="flex flex-col gap-1.5">

                  <label className="text-xs font-semibold text-slate-700">新密码 (留空则不修改)</label>

                  <input 

                    type="password" 

                    value={editUserPassword}

                    onChange={(e) => setEditUserPassword(e.target.value)}

                    placeholder="请输入新密码（不小于 6 位，留空表示不修改）"

                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-sm focus:outline-none focus:bg-white focus:border-blue-500"

                  />

                </div>



                <div className="flex flex-col gap-1.5">

                  <label className="text-xs font-semibold text-slate-700">所属公司</label>

                  <select 

                    value={editUserCompany}

                    onChange={(e) => setEditUserCompany(e.target.value)}

                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-sm focus:outline-none focus:bg-white focus:border-blue-500"

                  >

                    <option value="admin">admin</option>

                    {companiesList.filter((c) => c.name !== 'admin').map((c) => (

                      <option key={c.id} value={c.name}>{c.name}</option>

                    ))}

                  </select>

                </div>



                <div className="flex flex-col gap-1.5">

                  <label className="text-xs font-semibold text-slate-700">电报通知账号</label>

                  <input

                    type="text"

                    value={editUserTelegramContact}

                    onChange={(e) => setEditUserTelegramContact(e.target.value)}

                    placeholder="@username 或 t.me/username"

                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-sm focus:outline-none focus:bg-white focus:border-blue-500 font-mono"

                  />

                </div>



                <div className="flex flex-col gap-2">

                  <label className="text-xs font-semibold text-slate-700">角色权限</label>

                  <div className="flex gap-4">

                    <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none font-medium">

                      <input 

                        type="radio" 

                        name="editUserRole" 

                        value="user"

                        checked={editUserRole === 'user'}

                        onChange={() => setEditUserRole('user')}

                        className="text-blue-600 focus:ring-blue-500/20 border-slate-300"

                      />

                      <span>普通操作员</span>

                    </label>

                    <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none font-medium">

                      <input 

                        type="radio" 

                        name="editUserRole" 

                        value="admin"

                        checked={editUserRole === 'admin'}

                        onChange={() => setEditUserRole('admin')}

                        className="text-blue-600 focus:ring-blue-500/20 border-slate-300"

                      />

                      <span>系统管理员</span>

                    </label>

                  </div>

                </div>

              </div>



              <div className="p-5 border-t border-slate-100 flex justify-end gap-2.5 bg-slate-50/35">

                <button 

                  onClick={() => {

                    setShowEditUserModal(false);

                    setEditUserTarget(null);

                    setEditUserPassword('');

                    setEditUserTelegramContact('');

                  }}

                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-lg transition-all"

                >

                  取消

                </button>

                <button 

                  onClick={handleUpdateUser}

                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-all shadow-sm"

                >

                  确认修改

                </button>

              </div>

            </div>

          </div>

        )}



        {/* ADD COMPANY MODAL */}

        {showAddCompanyModal && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col overflow-hidden">

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">添加公司主体</h3>

                  <p className="text-xs text-slate-400 mt-0.5">创建一个新的公司主体用于隔离账号与系统用户</p>

                </div>

                <button 

                  onClick={() => {

                    setShowAddCompanyModal(false);

                    setNewCompanyName('');

                  }}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              <div className="p-6 flex flex-col gap-4">

                <div className="flex flex-col gap-1.5">

                  <label className="text-xs font-semibold text-slate-700">公司名称</label>

                  <input 

                    type="text" 

                    value={newCompanyName}

                    onChange={(e) => setNewCompanyName(e.target.value)}

                    placeholder="请输入公司名称"

                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-sm focus:outline-none focus:bg-white focus:border-blue-500 font-medium text-slate-800"

                  />

                </div>

              </div>



              <div className="p-5 border-t border-slate-100 flex justify-end gap-2.5 bg-slate-50/35">

                <button 

                  onClick={() => {

                    setShowAddCompanyModal(false);

                    setNewCompanyName('');

                  }}

                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-lg transition-all"

                >

                  取消

                </button>

                <button 

                  onClick={handleCreateCompany}

                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-all shadow-sm"

                >

                  确定添加

                </button>

              </div>

            </div>

          </div>

        )}



        {/* EDIT COMPANY MODAL */}

        {showEditCompanyModal && editCompanyTarget && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col overflow-hidden">

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">编辑公司主体</h3>

                  <p className="text-xs text-slate-400 mt-0.5">修改公司主体的显示名称</p>

                </div>

                <button 

                  onClick={() => {

                    setShowEditCompanyModal(false);

                    setEditCompanyTarget(null);

                    setEditCompanyNameValue('');

                  }}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              <div className="p-6 flex flex-col gap-4">

                <div className="flex flex-col gap-1.5">

                  <label className="text-xs font-semibold text-slate-700">公司名称</label>

                  <input 

                    type="text" 

                    value={editCompanyNameValue}

                    onChange={(e) => setEditCompanyNameValue(e.target.value)}

                    placeholder="请输入新的公司名称"

                    className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-sm focus:outline-none focus:bg-white focus:border-blue-500 font-medium text-slate-800"

                  />

                </div>

              </div>



              <div className="p-5 border-t border-slate-100 flex justify-end gap-2.5 bg-slate-50/35">

                <button 

                  onClick={() => {

                    setShowEditCompanyModal(false);

                    setEditCompanyTarget(null);

                    setEditCompanyNameValue('');

                  }}

                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-lg transition-all"

                >

                  取消

                </button>

                <button 

                  onClick={handleUpdateCompany}

                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-all shadow-sm"

                >

                  确认修改

                </button>

              </div>

            </div>

          </div>

        )}



        
        {/* LOGIN INFO MODAL */}
        {showLoginInfoModal && loginInfoAccount && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-lg flex flex-col max-h-[85vh] overflow-hidden">
              {/* Modal Header */}
              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <div>
                  <h3 className="font-bold text-slate-900 text-base">🔑 登录凭证与验证码</h3>
                  <p className="text-xs text-slate-400 mt-0.5 font-mono">{loginInfoAccount.name} (手机号: +{loginInfoAccount.id})</p>
                </div>
                <button 
                  onClick={() => {
                    setShowLoginInfoModal(false);
                    setLoginInfoAccount(null);
                  }}
                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <span className="text-lg">✕</span>
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6 overflow-y-auto flex flex-col gap-6">
                
                {/* 1. Captured Login Codes */}
                <div className="flex flex-col gap-3">
                  <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                    <span className="w-1.5 h-3 bg-blue-500 rounded-full"></span>
                    💬 实时设备验证码
                  </h4>
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 min-h-[100px] flex flex-col justify-center gap-4">
                    {loginInfoConnecting && (
                      <div className="text-center text-blue-600 text-xs py-3 flex flex-col items-center gap-2 border-b border-slate-100 pb-3">
                        <RefreshCw className="w-5 h-5 animate-spin text-blue-500" />
                        <p className="font-semibold">正在建立后台电报安全通道...</p>
                        <p className="text-[10px] text-slate-400">（由于网络原因，握手连接可能需要 15-20 秒）</p>
                      </div>
                    )}
                    {loginInfoError && (
                      <div className="text-center text-rose-500 text-xs py-3 border-b border-slate-100 pb-3">
                        <p className="font-semibold">❌ 建立通道失败: {loginInfoError}</p>
                        <p className="text-[10px] mt-1 text-slate-400">（如连接超时，可在下方直接获取已同步的历史通知）</p>
                      </div>
                    )}
                    {capturedRawMessages.length === 0 ? (
                      !loginInfoConnecting && !loginInfoError && (
                        <div className="text-center text-slate-400 text-xs py-4">
                          <p>等待官方发送通知消息...</p>
                          <p className="text-[10px] mt-1 text-slate-400/80">（请在此窗口保持打开状态下，在官方客户端发起登录）</p>
                        </div>
                      )
                    ) : (
                      <div className="flex flex-col gap-3">
                        <div className="text-[10px] text-slate-400 font-semibold">最近截获的设备验证码（自动解析）：</div>
                        <div className="flex flex-col gap-2.5">
                          {capturedRawMessages.map((item: any, idx: number) => {
                            const minutesAgo = Math.max(0, Math.round((Date.now() / 1000 - item.timestamp) / 60));
                            // Use word boundary regex to match 5-6 digit code cleanly, ignoring 777000
                            const matches = item.text.match(/\b\d{5,6}\b/g);
                            const parsedCode = matches ? matches.find((m: string) => m !== '777000') || '' : '';
                            
                            // If no code could be parsed, show a snippet or ignore
                            const displayCode = parsedCode ? parsedCode : '解析失败 (请查看控制台日志)';
                            
                            return (
                              <div key={idx} className="flex justify-between items-center bg-white p-3.5 border border-slate-200/60 rounded-xl shadow-2xs">
                                <div className="flex flex-col gap-1">
                                  <div className="flex items-center gap-2">
                                    <span className="text-[10px] text-blue-500 font-bold bg-blue-50 px-1.5 py-0.5 rounded-sm">🔑 验证码</span>
                                    <span className="text-[10px] text-slate-400">🕒 {new Date(item.timestamp * 1000).toLocaleTimeString()} ({minutesAgo === 0 ? "刚刚" : `${minutesAgo} 分钟前`})</span>
                                  </div>
                                  <span className="text-blue-600 font-mono font-bold text-lg tracking-wider select-all">{displayCode}</span>
                                </div>
                                <button
                                  onClick={() => {
                                    const copyText = parsedCode || item.text;
                                    navigator.clipboard.writeText(copyText);
                                    setToastText(parsedCode ? `验证码 ${parsedCode} 已复制` : "全文已复制");
                                    setTimeout(() => setToastText(''), 2000);
                                  }}
                                  className="px-3.5 py-1.5 bg-blue-50 hover:bg-blue-100 active:bg-blue-200 text-blue-600 text-xs font-bold rounded-lg transition-colors border border-blue-100 shadow-2xs"
                                >
                                  复制
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Connection Logs Console */}
                    <div className="flex flex-col gap-2 mt-2 pt-3 border-t border-slate-100">
                      <div className="text-[10px] text-slate-400 font-semibold flex justify-between items-center">
                        <span>🖥️ 后台连接日志：</span>
                        {loginInfoConnecting && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>}
                      </div>
                      <div ref={loginConnectionLogsRef} className="bg-sky-500 text-white font-mono text-[10px] p-3 rounded-lg max-h-[100px] overflow-y-auto flex flex-col gap-1 shadow-inner select-text">
                        {loginConnectionLogs.length === 0 ? (
                          <span className="text-sky-100">正在等待连接日志...</span>
                        ) : (
                          loginConnectionLogs.map((log: string, idx: number) => (
                            <div key={idx} className="leading-relaxed whitespace-pre-wrap">{log}</div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* 2. Page ID and 2FA Credentials */}
                <div className="flex flex-col gap-4 border-t border-slate-100 pt-5">
                  <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                    <span className="w-1.5 h-3 bg-blue-500 rounded-full"></span>
                    ⚙️ 配置云端凭证
                  </h4>
                  
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-col gap-1">
                      <label className="text-[10px] text-slate-400 font-semibold">页码ID (Page ID, 用于接码绑定)</label>
                      <input 
                        type="text" 
                        value={localPageId}
                        onChange={(e) => setLocalPageId(e.target.value)}
                        placeholder="请输入页码ID"
                        className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500 font-mono"
                      />
                    </div>

                    <div className="flex flex-col gap-1">
                      <label className="text-[10px] text-slate-400 font-semibold">两步验证密码 (2FA Password)</label>
                      <div className="flex gap-2">
                        <input 
                          type={showLoginInfo2faText ? "text" : "password"} 
                          value={local2fa}
                          onChange={(e) => setLocal2fa(e.target.value)}
                          placeholder="请输入两步验证密码"
                          className="flex-grow bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500 font-mono"
                        />
                        <button
                          type="button"
                          onClick={() => setShowLoginInfo2faText(!showLoginInfo2faText)}
                          className="px-3 bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-semibold rounded-lg border border-slate-200 transition-colors"
                        >
                          {showLoginInfo2faText ? "隐藏" : "显示"}
                        </button>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleUpdateLocalCredentials(loginInfoAccount.id)}
                    className="w-full mt-2 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-colors active:scale-[0.98] shadow-sm"
                  >
                    保存凭证配置
                  </button>
                </div>

              </div>
            </div>
          </div>
        )}

        {/* PRIVATE CHAT MODAL */}
        {showPrivateChatModal && privateChatAccount && (
          <div className="fixed inset-0 bg-slate-950/50 backdrop-blur-[2px] z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-7xl h-[86vh] flex flex-col overflow-hidden">
              <div className="h-[76px] px-5 border-b border-slate-200 flex items-center justify-between bg-white">
                <div className="min-w-0">
                  <h3 className="font-black text-slate-900 text-lg flex items-center gap-2">
                    <span className="w-9 h-9 rounded-xl bg-cyan-50 border border-cyan-100 text-cyan-700 flex items-center justify-center">
                      <MessageSquare className="w-4 h-4" />
                    </span>
                    私聊收件箱
                  </h3>
                  <p className="text-xs text-slate-400 mt-1 font-mono truncate pl-11">{privateChatAccount.name} / +{privateChatAccount.id}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => fetchPrivateDialogs(privateChatAccount.id)}
                    disabled={loadingPrivateDialogs}
                    className="w-9 h-9 rounded-xl border border-slate-200 bg-slate-50 hover:bg-white text-slate-600 flex items-center justify-center transition-colors disabled:opacity-50 shadow-sm"
                    title="刷新私聊"
                  >
                    <RefreshCw className={`w-4 h-4 ${loadingPrivateDialogs ? 'animate-spin' : ''}`} />
                  </button>
                  <button
                    onClick={() => {
                      setShowPrivateChatModal(false);
                      setPrivateChatAccount(null);
                      setSelectedPrivateDialog(null);
                      setPrivateMessages([]);
                      fetchPrivateUnreadSummary();
                    }}
                    className="w-9 h-9 rounded-xl hover:bg-slate-100 flex items-center justify-center text-slate-400 hover:text-slate-700 transition-colors"
                    title="关闭"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              <div className="flex flex-1 min-h-0 bg-slate-100/60">
                <aside className="w-[360px] border-r border-slate-200 bg-white flex flex-col min-h-0">
                  <div className="px-4 py-4 border-b border-slate-100 flex items-center justify-between">
                    <div>
                      <div className="text-sm font-black text-slate-800">Private Chats</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">One-to-one messages</div>
                    </div>
                    <span className="min-w-7 h-7 px-2 rounded-full bg-cyan-50 text-cyan-700 text-xs font-black border border-cyan-100 flex items-center justify-center">
                      {privateDialogs.length}
                    </span>
                  </div>
                  <div className="flex-1 overflow-y-auto bg-slate-50/60 p-2">
                    {loadingPrivateDialogs && privateDialogs.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-slate-400 gap-2 text-xs">
                        <RefreshCw className="w-6 h-6 animate-spin text-cyan-500" />
                        正在加载私聊...
                      </div>
                    ) : privateDialogs.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-slate-400 gap-2 text-xs px-6 text-center">
                        <MessageSquare className="w-8 h-8 opacity-30" />
                        暂无私聊会话
                      </div>
                    ) : (
                      privateDialogs
                        .filter(dialog => !dialog.is_bot && !String(dialog.username || '').trim().replace(/^@/, '').toLowerCase().endsWith('bot'))
                        .map(dialog => {
                        const active = selectedPrivateDialog?.peer_id === dialog.peer_id;
                        return (
                          <button
                            key={dialog.peer_id}
                            onClick={() => handleSelectPrivateDialog(privateChatAccount.id, dialog)}
                            className={`w-full px-3.5 py-3 text-left rounded-xl flex gap-3 transition-all mb-1.5 border ${
                              active
                                ? 'bg-white border-cyan-200 shadow-sm ring-1 ring-cyan-100'
                                : 'bg-white/80 border-transparent hover:bg-white hover:border-slate-200 hover:shadow-sm'
                            }`}
                          >
                            <div className={`w-11 h-11 rounded-2xl flex items-center justify-center text-sm font-black flex-shrink-0 ${active ? 'bg-cyan-600 text-white shadow-sm' : 'bg-slate-100 text-slate-500'}`}>
                              {(dialog.name || dialog.username || '?').slice(0, 1).toUpperCase()}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-sm font-bold text-slate-800 truncate">{dialog.name}</span>
                                {dialog.unread_count > 0 ? (
                                  <span className="min-w-5 h-5 px-1.5 rounded-full bg-rose-500 text-white text-[10px] font-bold flex items-center justify-center">
                                    {dialog.unread_count}
                                  </span>
                                ) : dialog.last_message_at ? (
                                  <span className="text-[10px] text-slate-400 font-mono shrink-0">
                                    {new Date(dialog.last_message_at).toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })}
                                  </span>
                                ) : null}
                              </div>
                              <div className="text-[11px] text-cyan-600 font-mono truncate">{dialog.username || (dialog.phone ? `+${dialog.phone}` : `ID ${dialog.peer_id}`)}</div>
                              <div className="text-xs text-slate-500 truncate mt-1">{dialog.last_message || (dialog.is_bot ? 'Bot private chat' : 'No text message')}</div>
                            </div>
                          </button>
                        );
                      })
                    )}
                  </div>
                </aside>

                <section className="flex-1 min-w-0 flex flex-col bg-white">
                  {selectedPrivateDialog ? (
                    <>
                      <div className="h-[72px] px-6 border-b border-slate-200 bg-white flex items-center justify-between">
                        <div className="min-w-0 flex items-center gap-3">
                          <div className="w-10 h-10 rounded-2xl bg-slate-100 text-slate-600 flex items-center justify-center text-sm font-black">
                            {(selectedPrivateDialog.name || selectedPrivateDialog.username || '?').slice(0, 1).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <div className="text-base font-black text-slate-900 truncate">{selectedPrivateDialog.name}</div>
                            <div className="text-xs text-slate-400 font-mono truncate">{selectedPrivateDialog.username || `ID ${selectedPrivateDialog.peer_id}`}</div>
                          </div>
                        </div>
                        {selectedPrivateDialog.is_bot && (
                          <span className="px-2 py-1 rounded-md bg-blue-50 text-blue-700 text-[10px] font-bold border border-blue-100">BOT</span>
                        )}
                      </div>

                      {privateChatError && (
                        <div className="mx-5 mt-3 px-3 py-2 rounded-lg border border-rose-100 bg-rose-50 text-rose-700 text-xs">
                          {privateChatError}
                        </div>
                      )}

                      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-3 bg-[radial-gradient(circle_at_top_left,rgba(8,145,178,0.08),transparent_32%),linear-gradient(180deg,#ffffff,#f8fafc)]">
                        {loadingPrivateMessages && privateMessages.length === 0 ? (
                          <div className="h-full flex items-center justify-center text-slate-400 text-xs gap-2">
                            <RefreshCw className="w-5 h-5 animate-spin text-cyan-500" />
                            正在加载消息...
                          </div>
                        ) : privateMessages.length === 0 ? (
                          <div className="h-full flex flex-col items-center justify-center text-slate-400 gap-2 text-xs">
                            <MessageSquare className="w-8 h-8 opacity-30" />
                            没有可显示的文本消息
                          </div>
                        ) : (
                          privateMessages.map(msg => (
                            <div key={msg.id} className={`flex ${msg.out ? 'justify-end' : 'justify-start'}`}>
                              <div className={`max-w-[68%] rounded-2xl px-4 py-3 shadow-sm border text-sm leading-relaxed ${
                                msg.out
                                  ? 'bg-cyan-600 text-white border-cyan-600 rounded-br-md shadow-cyan-900/10'
                                  : 'bg-white text-slate-800 border-slate-200 rounded-bl-md'
                              }`}>
                                <div className="whitespace-pre-wrap break-words">{msg.text || (msg.has_media ? '[media]' : '')}</div>
                                <div className={`text-[10px] mt-1 text-right ${msg.out ? 'text-cyan-100' : 'text-slate-400'}`}>
                                  {msg.status === 'queued' ? '排队中' : msg.status === 'failed' ? '发送失败' : (msg.date ? new Date(msg.date).toLocaleString('zh-CN', { hour12: false }) : '')}
                                </div>
                              </div>
                            </div>
                          ))
                        )}
                        <div ref={privateMessagesEndRef} className="h-px" />
                      </div>

                      <div className="p-4 border-t border-slate-200 bg-white">
                        <div className="flex items-end gap-3">
                          <textarea
                            value={privateMessageDraft}
                            onChange={(e) => setPrivateMessageDraft(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSendPrivateMessage();
                              }
                            }}
                            placeholder="输入私聊消息，Enter 发送，Shift+Enter 换行"
                            className="flex-1 min-h-[46px] max-h-32 resize-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 focus:outline-none focus:border-cyan-500 focus:bg-white focus:ring-2 focus:ring-cyan-500/10"
                          />
                          <button
                            onClick={handleSendPrivateMessage}
                            disabled={sendingPrivateMessage || !privateMessageDraft.trim()}
                            className="w-12 h-12 rounded-2xl bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-300 text-white flex items-center justify-center transition-colors shadow-sm"
                            title="发送"
                          >
                            {sendingPrivateMessage ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-slate-400 gap-2 text-xs">
                      <MessageSquare className="w-10 h-10 opacity-30" />
                      选择左侧私聊查看消息
                    </div>
                  )}
                </section>
              </div>
            </div>
          </div>
        )}

        {/* D. SLEKE ACCOUNTS MANAGEMENT MODAL DIALOG */}

        {showManageModal && modalAccount && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-lg flex flex-col max-h-[85vh] overflow-hidden">

              

              {/* Modal Header */}

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">账号设置管理</h3>

                  <p className="text-xs text-slate-400 mt-0.5 font-mono">{modalAccount.name} (ID: {modalAccount.id})</p>

                </div>

                <div className="flex items-center gap-2">

                  <button

                    type="button"

                    onClick={async () => {

                      if (confirm(`确定要清除账号 ${modalAccount.id} 的 Session (强制退出登录) 吗？`)) {

                        await handleClearBackendAccountSession(modalAccount.id);

                        setShowManageModal(false);

                        setModalAccount(null);

                      }

                    }}

                    className="px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-700 hover:text-amber-800 rounded-lg text-xs font-bold transition-colors border border-amber-200 flex items-center gap-1 active:scale-[0.98]"

                  >

                    <span>退出登录</span>

                  </button>

                  <button 

                    onClick={() => {

                      setShowManageModal(false);

                      setModalAccount(null);

                      setSelectedSingleAvatarFile(null);

                      setSelectedSingleLibraryAvatarName('');

                    }}

                    className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                  >

                    <X className="w-5 h-5" />

                  </button>

                </div>

              </div>



              {/* Modal Body */}

              <div className="p-6 overflow-y-auto flex flex-col gap-6">

                

                {/* Account Profile Status */}

                <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 flex flex-col gap-2 text-xs">

                  <div className="font-semibold text-slate-700 text-xs mb-1">当前云端信息</div>

                  <div className="flex justify-between">

                    <span className="text-slate-400">电报账户：</span>

                    <span className="text-slate-800 font-semibold truncate max-w-[280px]" title={modalAccount.meInfo}>

                      {modalAccount.meInfo || '未知'}

                    </span>

                  </div>

                </div>



                {/* 1. Modify Profile Name */}

                <div className="flex flex-col gap-3">

                  <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">

                    <span className="w-1.5 h-3 bg-blue-500 rounded-full"></span>

                    👤 修改个人姓名

                  </h4>

                  <div className="grid grid-cols-2 gap-3">

                    <div className="flex flex-col gap-1">

                      <label className="text-[10px] text-slate-400 font-semibold">名字 (First Name)</label>

                      <input 

                        type="text" 

                        value={editFirstName}

                        onChange={(e) => setEditFirstName(e.target.value)}

                        placeholder="名字"

                        className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                      />

                    </div>

                    <div className="flex flex-col gap-1">

                      <label className="text-[10px] text-slate-400 font-semibold">姓氏 (Last Name, 可空)</label>

                      <input 

                        type="text" 

                        value={editLastName}

                        onChange={(e) => setEditLastName(e.target.value)}

                        placeholder="姓氏"

                        className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                      />

                    </div>

                  </div>

                  <button

                    onClick={async () => {

                      await handleUpdateProfileName(modalAccount.id);

                      checkAccountLoginStatus(modalAccount.id, backendAccounts.findIndex(a => a.id === modalAccount.id))

                        .then(() => {

                          const updated = backendAccounts.find(a => a.id === modalAccount.id);

                          if (updated) setModalAccount(updated);

                        });

                    }}

                    className="self-end px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-colors active:scale-[0.98] shadow-sm"

                  >

                    保存姓名修改

                  </button>

                </div>



                {/* 2. Modify Profile Username */}

                <div className="flex flex-col gap-3">

                  <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">

                    <span className="w-1.5 h-3 bg-blue-500 rounded-full"></span>

                    🏷️ 修改用户名 (Username)

                  </h4>

                  <div className="flex flex-col gap-1">

                    <label className="text-[10px] text-slate-400 font-semibold">用户名 (@username)</label>

                    <div className="flex gap-2">

                      <div className="flex-grow relative">

                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs font-mono font-medium">@</span>

                        <input 

                          type="text" 

                          value={editUsername}

                          onChange={(e) => setEditUsername(e.target.value)}

                          placeholder="新用户名"

                          className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-6 pr-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500 font-mono"

                        />

                      </div>

                      <button

                        onClick={async () => {

                          await handleUpdateProfileUsername(modalAccount.id);

                          checkAccountLoginStatus(modalAccount.id, backendAccounts.findIndex(a => a.id === modalAccount.id))

                            .then(() => {

                              const updated = backendAccounts.find(a => a.id === modalAccount.id);

                              if (updated) setModalAccount(updated);

                            });

                        }}

                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-colors active:scale-[0.98] shadow-sm shrink-0"

                      >

                        保存用户名

                      </button>

                    </div>

                  </div>

                </div>



                {/* 3. Modify 2FA Password */}

                <div className="flex flex-col gap-3 border-t border-slate-100 pt-5">

                  <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">

                    <span className="w-1.5 h-3 bg-blue-500 rounded-full"></span>

                    🔑 修改两步验证密码 (2FA)

                  </h4>

                  <div className="grid grid-cols-2 gap-3">

                    <div className="flex flex-col gap-1 col-span-2">

                      <label className="text-[10px] text-slate-400 font-semibold">原两步验证密码 (若当前未设置请留空)</label>

                      <input 

                        type="password" 

                        value={edit2faCurrentPassword}

                        onChange={(e) => setEdit2faCurrentPassword(e.target.value)}

                        placeholder="输入当前2FA密码"

                        className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500 font-mono"

                        disabled={updating2fa}

                      />

                    </div>

                    <div className="flex flex-col gap-1">

                      <label className="text-[10px] text-slate-400 font-semibold">新两步验证密码</label>

                      <input 

                        type="text" 

                        value={edit2faNewPassword}

                        onChange={(e) => setEdit2faNewPassword(e.target.value)}

                        placeholder="新密码"

                        className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500 font-mono"

                        disabled={updating2fa}

                      />

                    </div>

                    <div className="flex flex-col gap-1">

                      <label className="text-[10px] text-slate-400 font-semibold">密码提示信息 (Hint, 可空)</label>

                      <input 

                        type="text" 

                        value={edit2faHint}

                        onChange={(e) => setEdit2faHint(e.target.value)}

                        placeholder="密码提示"

                        className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                        disabled={updating2fa}

                      />

                    </div>

                  </div>

                  <button

                    onClick={() => handleUpdateAccount2fa(modalAccount.id)}

                    disabled={updating2fa}

                    className="self-end px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-colors active:scale-[0.98] shadow-sm flex items-center gap-1"

                  >

                    {updating2fa && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}

                    <span>修改两步验证</span>

                  </button>

                </div>



                {/* 3. Add Group Folder (Temporarily Hidden from UI) */}

                {/*

                <div className="flex flex-col gap-3 border-t border-slate-100 pt-5">

                  <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">

                    <span className="w-1.5 h-3 bg-blue-500 rounded-full"></span>

                    📂 添加群组文件夹

                  </h4>

                  <div className="flex flex-col gap-3">

                    <div className="flex flex-col gap-1.5">

                      <label className="text-[10px] text-slate-400 font-semibold">快速选择预设文件夹</label>

                      <div className="flex gap-2">

                        <button 

                          onClick={() => {

                            setNewFolderTitle('内部');

                            setFolderCategories(['groups', 'broadcasts']);

                          }}

                          className={`flex-grow py-2 border rounded-lg text-xs font-semibold transition-all ${

                            newFolderTitle === '内部' 

                              ? 'border-blue-500 bg-blue-50/50 text-blue-600' 

                              : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'

                          }`}

                        >

                          🔒 内部

                        </button>

                        <button 

                          onClick={() => {

                            setNewFolderTitle('广告');

                            setFolderCategories(['groups', 'broadcasts']);

                          }}

                          className={`flex-grow py-2 border rounded-lg text-xs font-semibold transition-all ${

                            newFolderTitle === '广告' 

                              ? 'border-blue-500 bg-blue-50/50 text-blue-600' 

                              : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'

                          }`}

                        >

                          📢 广告

                        </button>

                      </div>

                    </div>



                    <div className="flex flex-col gap-1">

                      <label className="text-[10px] text-slate-400 font-semibold">自定义文件夹名称</label>

                      <input 

                        type="text" 

                        value={newFolderTitle}

                        onChange={(e) => setNewFolderTitle(e.target.value)}

                        placeholder="输入文件夹名称"

                        className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                      />

                    </div>

                    

                    <div className="flex flex-col gap-1.5">

                      <label className="text-[10px] text-slate-400 font-semibold">包含聊天类别 (默认包含群组和频道)</label>

                      <div className="grid grid-cols-2 gap-2">

                        {[

                          { key: 'groups', label: '群组 (Groups)' },

                          { key: 'broadcasts', label: '频道 (Channels)' },

                          { key: 'contacts', label: '联系人 (Contacts)' },

                          { key: 'non_contacts', label: '非联系人' },

                          { key: 'bots', label: '机器人 (Bots)' }

                        ].map((cat) => (

                          <label key={cat.key} className="flex items-center gap-1.5 text-xs cursor-pointer select-none text-slate-600 font-medium">

                            <input 

                              type="checkbox" 

                              checked={folderCategories.includes(cat.key)}

                              onChange={(e) => {

                                if (e.target.checked) {

                                  setFolderCategories(prev => [...prev, cat.key]);

                                } else {

                                  setFolderCategories(prev => prev.filter(k => k !== cat.key));

                                }

                              }}

                              className="rounded text-blue-600 focus:ring-blue-500/20 border-slate-300"

                            />

                            <span>{cat.label}</span>

                          </label>

                        ))}

                      </div>

                    </div>



                    <button

                      onClick={() => handleCreateChatFolder(modalAccount.id)}

                      className="self-end px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-colors active:scale-[0.98] shadow-sm mt-1"

                    >

                      添加群组文件夹

                    </button>

                  </div>

                </div>

                */}







                {/* 4. 更换账户头像 (Change Account Avatar) */}

                <div className="flex flex-col gap-3 border-t border-slate-100 pt-5">

                  <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">

                    <span className="w-1.5 h-3 bg-blue-500 rounded-full"></span>

                    🖼️ 更换账户头像

                  </h4>

                  

                  {/* Select source: local or library */}

                  <div className="flex bg-slate-100 p-0.5 rounded-lg shrink-0">

                    <button

                      type="button"

                      onClick={() => setSingleAvatarSource('local')}

                      className={`flex-1 py-1 text-center text-[10px] font-semibold rounded-md transition-all ${

                        singleAvatarSource === 'local' 

                          ? 'bg-white text-slate-800 shadow-xs' 

                          : 'text-slate-500 hover:text-slate-800'

                      }`}

                    >

                      本地图片上传

                    </button>

                    <button

                      type="button"

                      onClick={() => {

                        setSingleAvatarSource('library');

                        fetchAvatarLibrary();

                      }}

                      className={`flex-1 py-1 text-center text-[10px] font-semibold rounded-md transition-all ${

                        singleAvatarSource === 'library' 

                          ? 'bg-white text-slate-800 shadow-xs' 

                          : 'text-slate-500 hover:text-slate-800'

                      }`}

                    >

                      从头像库选择

                    </button>

                  </div>



                  {singleAvatarSource === 'local' ? (

                    <div className="flex flex-col gap-2">

                      <input 

                        type="file" 

                        accept="image/*"

                        onChange={(e) => {

                          if (e.target.files && e.target.files.length > 0) {

                            setSelectedSingleAvatarFile(e.target.files[0]);

                          }

                        }}

                        className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                        disabled={updatingAvatar}

                      />

                      {selectedSingleAvatarFile && (

                        <p className="text-[10px] text-slate-500 font-mono truncate">

                          已选择：{selectedSingleAvatarFile.name} ({(selectedSingleAvatarFile.size / 1024).toFixed(1)} KB)

                        </p>

                      )}

                    </div>

                  ) : (

                    <div className="flex flex-col gap-2">

                      {avatarLibrary.length === 0 ? (

                        <div className="text-center py-4 text-slate-400 border border-dashed border-slate-200 rounded-lg bg-slate-50/20 text-[11px]">

                          头像库目前为空。请在主页面点击“头像库管理”上传头像。

                        </div>

                      ) : (

                        <div className="grid grid-cols-5 gap-2 max-h-[120px] overflow-y-auto p-1 border border-slate-100 rounded-lg bg-slate-50/30">

                          {avatarLibrary.map((item) => {

                            const isSelected = selectedSingleLibraryAvatarName === item.name;

                            const backendUrl = BASE_URL;

                            const imgUrl = `${backendUrl}/api/avatar-library/file/${encodeURIComponent(item.name)}`;



                            return (

                              <div 

                                key={item.name}

                                onClick={() => setSelectedSingleLibraryAvatarName(item.name)}

                                className={`relative aspect-square rounded-lg overflow-hidden border-2 cursor-pointer transition-all select-none hover:scale-[1.03] ${

                                  isSelected ? 'border-blue-500 ring-2 ring-blue-500/15' : 'border-slate-100 hover:border-slate-300'

                                }`}

                                title={item.name}

                              >

                                <img src={imgUrl} alt={item.name} className="w-full h-full object-cover" />

                                {isSelected && (

                                  <div className="absolute inset-0 bg-blue-500/20 flex items-center justify-center">

                                    <div className="bg-blue-600 text-white rounded-full p-0.5">

                                      <Check className="w-2.5 h-2.5" />

                                    </div>

                                  </div>

                                )}

                              </div>

                            );

                          })}

                        </div>

                      )}

                    </div>

                  )}



                  <button

                    onClick={async () => {

                      if (singleAvatarSource === 'local') {

                        if (!selectedSingleAvatarFile) {

                          alert("请先选择图片文件！");

                          return;

                        }

                        await handleUpdateProfileAvatar(modalAccount.id, selectedSingleAvatarFile);

                      } else {

                        if (!selectedSingleLibraryAvatarName) {

                          alert("请从头像库选择一张头像！");

                          return;

                        }

                        await handleUpdateProfileAvatar(modalAccount.id, null, selectedSingleLibraryAvatarName);

                      }

                      // Clear inputs after update

                      setSelectedSingleAvatarFile(null);

                      setSelectedSingleLibraryAvatarName('');

                    }}

                    disabled={updatingAvatar}

                    className="self-end px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-xs font-bold rounded-lg transition-colors active:scale-[0.98] shadow-sm flex items-center gap-1"

                  >

                    {updatingAvatar && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}

                    <span>更新头像</span>

                  </button>

                </div>



                {/* 5. 活跃登录设备 (Active Login Sessions) */}

                <div className="flex flex-col gap-3 border-t border-slate-100 pt-5">

                  <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">

                    <span className="w-1.5 h-3 bg-blue-500 rounded-full"></span>

                    💻 活跃登录设备

                  </h4>



                  {loadingDevices ? (

                    <div className="flex items-center justify-center py-6 text-slate-400 gap-2">

                      <RefreshCw className="w-4 h-4 animate-spin text-blue-500" />

                      <span className="text-xs font-light">正在加载设备会话...</span>

                    </div>

                  ) : devicesError ? (

                    <div className="text-center py-6 text-rose-500 border border-dashed border-rose-200 rounded-xl bg-rose-50/20 text-xs flex flex-col gap-2 items-center justify-center">

                      <span>加载设备失败：{devicesError}</span>

                      <button 

                        onClick={() => fetchAccountDevices(modalAccount.id)}

                        className="px-2.5 py-1 bg-white hover:bg-slate-50 border border-rose-200 text-rose-600 rounded-lg text-[10px] font-bold transition-all active:scale-[0.98] cursor-pointer"

                      >

                        重试

                      </button>

                    </div>

                  ) : accountDevices.length === 0 ? (

                    <div className="text-center py-6 text-slate-400 border border-dashed border-slate-200 rounded-xl bg-slate-50/20 text-xs">

                      没有获取到活跃登录设备会话。

                    </div>

                  ) : (

                    <div className="flex flex-col gap-2 max-h-[220px] overflow-y-auto pr-1">

                      {accountDevices.map((dev) => (

                        <div 

                          key={dev.hash} 

                          className={`flex items-center justify-between p-3 border rounded-xl transition-all ${

                            dev.current 

                              ? 'border-emerald-100 bg-emerald-50/15' 

                              : 'border-slate-100 bg-slate-50/25 hover:bg-slate-50/50'

                          }`}

                        >

                          <div className="flex flex-col gap-1 text-[11px] leading-normal select-text">

                            <div className="flex items-center gap-1.5">

                              <span className="font-bold text-slate-800">

                                {dev.platform} {dev.device_model}

                              </span>

                              {dev.current ? (

                                <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100">

                                  当前会话

                                </span>

                              ) : (

                                <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-slate-100 text-slate-500 border border-slate-200">

                                  其它设备

                                </span>

                              )}

                            </div>

                            <div className="text-slate-500">

                              应用：{dev.app_name} ({dev.app_version}) | API ID: {dev.api_id}

                            </div>

                            <div className="text-slate-400 font-mono text-[10px]">

                              IP：{dev.ip} ({dev.region || dev.country || '位置未知'})

                            </div>

                            <div className="text-slate-400 text-[10px]">

                              活跃时间：{new Date(dev.date_active).toLocaleString()}

                            </div>

                          </div>



                          {!dev.current && (

                            <button

                              onClick={() => handleKickDevice(modalAccount.id, dev.hash)}

                              className="px-2.5 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-600 hover:text-rose-700 text-[10px] font-bold rounded-lg border border-rose-100 transition-colors shrink-0"

                            >

                              踢下线

                            </button>

                          )}

                        </div>

                      ))}

                    </div>

                  )}

                </div>



              </div>



              {/* Modal Footer */}

              <div className="p-5 border-t border-slate-100 flex justify-end bg-slate-50/35">

                <button 

                  onClick={() => {

                    setShowManageModal(false);

                    setModalAccount(null);

                  }}

                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-lg transition-all"

                >

                  关闭

                </button>

              </div>



            </div>

          </div>

        )}

        {/* HEALTH SCORE DETAILS & ANTI-BAN TIPS MODAL */}

        {showHealthDetailsModal && healthDetailsAccount && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col max-h-[85vh] overflow-hidden animate-fade-in">

              

              {/* Modal Header */}

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base flex items-center gap-1.5">

                    <Shield className="w-5 h-5 text-blue-500" />

                    <span>账号健康及风控详情</span>

                  </h3>

                  <p className="text-xs text-slate-400 mt-0.5 font-mono">

                    {healthDetailsAccount.name} (手机号: +{healthDetailsAccount.id})

                  </p>

                </div>

                <button 

                  onClick={() => {

                    setShowHealthDetailsModal(false);

                    setHealthDetailsAccount(null);

                  }}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              {/* Modal Body */}

              <div className="p-6 overflow-y-auto flex flex-col gap-5">

                

                {/* 1. Account Profile Status & Health Score */}

                <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 flex flex-col gap-2.5 text-xs">

                  <div className="flex justify-between">

                    <span className="text-slate-400">当前电报账户：</span>

                    <span className="text-slate-800 font-semibold truncate max-w-[220px]" title={healthDetailsAccount.meInfo}>

                      {healthDetailsAccount.meInfo || '未知'}

                    </span>

                  </div>

                  

                  <div className="flex justify-between items-center border-t border-slate-200/60 pt-2.5">

                    <span className="text-slate-400">健康评分：</span>

                    {(() => {

                      const score = calculateHealthScore(healthDetailsAccount);

                      let colorClass = "text-rose-600";

                      let desc = "异常状态";

                      if (score === 100) {

                        colorClass = "text-emerald-600";

                        desc = "正常 (无限制)";

                      } else if (score === 50) {

                        colorClass = "text-amber-600";

                        desc = "一般 (受限制)";

                      } else if (score === 0) {

                        if (healthDetailsAccount.is_deactivated) {

                          colorClass = "text-rose-700";

                          desc = "账号已被注销";

                        } else {

                          colorClass = "text-slate-400";

                          desc = "未登录";

                        }

                      }

                      return (

                        <div className="flex flex-col items-end gap-0.5">

                          <span className={`font-bold text-sm ${colorClass}`}>{score} / 100 分</span>

                          <span className="text-[10px] text-slate-400 font-light">{desc}</span>

                        </div>

                      );

                    })()}

                  </div>



                  <div className="border-t border-slate-200/60 pt-2.5 flex flex-col gap-1.5">

                    <div className="flex justify-between items-center">

                      <div className="flex flex-col">

                        <span className="text-slate-500 font-semibold text-xs">SpamBot 反馈详情</span>

                        <span className="text-[9px] text-slate-400 font-light mt-0.5">

                          {healthDetailsAccount.spambot_time 

                            ? `上次检测：${new Date(healthDetailsAccount.spambot_time * 1000).toLocaleString('zh-CN', { hour12: false })}` 

                            : '上次检测：暂无记录'}

                        </span>

                      </div>

                      {healthDetailsAccount.isAuthorized && !healthDetailsAccount.is_deactivated && (

                        <button

                          onClick={() => handleRefreshHealthDetails(healthDetailsAccount.id)}

                          disabled={checkingHealth}

                          className="px-2.5 py-1 bg-blue-50 hover:bg-blue-100 disabled:bg-slate-100 text-blue-600 disabled:text-slate-400 rounded-md text-[10px] font-bold transition-all active:scale-[0.98] cursor-pointer border border-blue-200/40"

                        >

                          {checkingHealth ? '正在检测...' : '同步/检测风控状态'}

                    </button>

                  )}

                </div>

                <pre className="text-[10px] text-slate-600 bg-slate-100/60 p-2.5 rounded-lg font-sans whitespace-pre-wrap leading-relaxed max-h-[140px] overflow-y-auto mt-1 border border-slate-200/40 select-text">

                  {checkingHealth 

                    ? '正在向 @SpamBot 发送指令进行实时风控检测，这需要数秒时间，请稍候...' 

                    : (healthDetailsAccount.spambot_details || '尚未拉取状态，请点击上方按钮进行实时风控检测。')}

                </pre>

                  </div>

                </div>



                {/* 2. Health Rating explanation and anti-ban tips */}

                <div className="bg-blue-50/40 rounded-xl p-4 border border-blue-100/60 flex flex-col gap-2.5 text-xs text-slate-700">

                  <div className="font-bold text-blue-800 text-xs flex items-center gap-1.5">

                    <span>💡 电报官方账号安全及防封建议</span>

                  </div>

                  <div className="flex flex-col gap-2 leading-relaxed text-[11px]">

                    <div className="flex items-start gap-1.5">

                      <span className="text-blue-500 font-bold">•</span>

                      <span><strong>启用两步验证 (2FA)：</strong> 官方安全核心，极大提高账号防风控权重。</span>

                    </div>

                    <div className="flex items-start gap-1.5">

                      <span className="text-blue-500 font-bold">•</span>

                      <span><strong>完善个人资料：</strong> 务必上传头像和设置唯一的用户名，空白账户极易被系统Antispam防垃圾判定为垃圾账号秒封。</span>

                    </div>

                    <div className="flex items-start gap-1.5">

                      <span className="text-blue-500 font-bold">•</span>

                      <span><strong>新号正常养号：</strong> 刚加入的账号建议正常养号 7-14 天，禁止立即大量加群、批量拉群或主动私发群发。</span>

                    </div>

                    <div className="flex items-start gap-1.5">

                      <span className="text-blue-500 font-bold">•</span>

                      <span><strong>避免群友垃圾举报：</strong> 减少发送无意义刷屏或虚假广告。若被多个群成员点击“Report Spam (举报垃圾群发)”，账号将被立刻限流或禁言。</span>

                    </div>

                  </div>

                </div>



              </div>



              {/* Modal Footer */}

              <div className="p-4 border-t border-slate-100 flex justify-end bg-slate-50/50">

                <button

                  type="button"

                  onClick={() => {

                    setShowHealthDetailsModal(false);

                    setHealthDetailsAccount(null);

                  }}

                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 transition-colors"

                >

                  关闭

                </button>

              </div>



            </div>

          </div>

        )}

        {/* J. CREATE CAMPAIGN TASK MODAL */}

        {showCreateCampaignModal && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-4xl flex flex-col max-h-[90vh] overflow-hidden">

              

              {/* Modal Header */}

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">🚀 新建广告轰炸任务</h3>

                  <p className="text-xs text-slate-400 mt-0.5">配置目标群组、循环间隔与发送内容</p>

                </div>

                <button 

                  onClick={() => setShowCreateCampaignModal(false)}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              {/* Modal Body */}

              <div className="p-6 overflow-y-auto flex-grow bg-slate-50/20 grid grid-cols-1 lg:grid-cols-3 gap-6">

                

                {/* Left Column: Account & Group Select */}

                <div className="lg:col-span-2 flex flex-col gap-4 bg-white border border-slate-150 rounded-2xl p-5 shadow-xs">

                  <div className="flex flex-col gap-1.5">

                    <div className="flex justify-between items-center">

                      <label className="text-xs font-bold text-slate-600">执行账号 (可多选)</label>

                      <button

                        type="button"

                        onClick={() => {

                          const selectableCampaignAccountIds = backendAccounts.filter(isAccountSelectableForTask).map(acc => acc.id);

                          if (selectedCampaignAccountIds.length === selectableCampaignAccountIds.length) {

                            setSelectedCampaignAccountIds([]);

                            setNewCampaignAccountId('');

                          } else {

                            setSelectedCampaignAccountIds(selectableCampaignAccountIds);

                            if (selectableCampaignAccountIds.length === 1) {

                              setNewCampaignAccountId(selectableCampaignAccountIds[0]);

                              fetchCampaignFoldersGroups(selectableCampaignAccountIds[0]);

                              fetchCampaignLastParams(selectableCampaignAccountIds[0]);

                            } else {

                              setNewCampaignAccountId('');

                              if (selectableCampaignAccountIds.length > 1) {
                                setCampaignInputMode('library');
                              }

                            }

                          }

                        }}

                        className="text-xs text-blue-600 hover:text-blue-700 font-semibold"

                      >

                        {selectedCampaignAccountIds.length === backendAccounts.filter(isAccountSelectableForTask).length ? "取消全选" : "全选可执行账号"}

                      </button>

                    </div>

                    <div className="border border-slate-200 rounded-xl p-3 bg-slate-50/50 max-h-36 overflow-y-auto flex flex-col gap-2">

                      {backendAccounts.filter(acc => isAccountSelectableForTask(acc) || selectedCampaignAccountIds.includes(acc.id)).map(acc => {

                        const isChecked = selectedCampaignAccountIds.includes(acc.id);
                        const isSelectable = isAccountSelectableForTask(acc);
                        const disabledReason = getAccountTaskStateLabel(acc);
                        const isDisabled = !isSelectable && !isChecked;

                        return (

                          <label key={acc.id} className={`flex items-center gap-2 text-xs font-medium text-slate-700 select-none ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>

                            <input

                              type="checkbox"

                              checked={isChecked}

                              disabled={isDisabled}

                              onChange={(e) => {
                                 if (!isSelectable && !isChecked) return;

                                let nextIds = [...selectedCampaignAccountIds];

                                if (e.target.checked) {

                                  if (!nextIds.includes(acc.id)) {

                                    nextIds.push(acc.id);

                                  }

                                } else {

                                  nextIds = nextIds.filter(id => id !== acc.id);

                                }

                                setSelectedCampaignAccountIds(nextIds);

                                

                                if (nextIds.length === 1) {

                                  setNewCampaignAccountId(nextIds[0]);

                                  fetchCampaignFoldersGroups(nextIds[0]);

                                  fetchCampaignLastParams(nextIds[0]);

                                } else {

                                  setNewCampaignAccountId('');

                                  setCampaignInputMode('library');

                                }

                              }}

                              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-4 h-4"

                            />

                            <span>{acc.name} <span className="font-mono text-slate-400">({acc.id})</span></span>

                             {!isSelectable && disabledReason && (
                               <span className="text-red-500 font-semibold ml-auto text-[10px] flex items-center gap-1">
                                 ❗ {disabledReason}
                              </span>
                            )}
                          </label>

                        );

                      })}

                    </div>

                  </div>



                  {selectedCampaignAccountIds.length === 0 && (

                    <div className="flex-grow flex flex-col items-center justify-center py-20 text-slate-400 gap-2 border border-dashed border-slate-200 rounded-xl bg-slate-50/20">

                      <Users className="w-8 h-8 opacity-30" />

                      <span className="text-xs">请先选择执行任务的账号</span>

                    </div>

                  )}



                  {selectedCampaignAccountIds.length > 1 && (

                    <div className="flex-grow flex flex-col gap-4 min-h-[300px]">

                      <div className="flex border-b border-slate-150 mb-2">
                        <button
                          type="button"
                          onClick={() => setCampaignInputMode('library')}
                          className={`px-4 py-2 text-xs font-bold transition-all border-b-2 -mb-px ${
                            campaignInputMode === 'library'
                              ? 'border-blue-600 text-blue-600'
                              : 'border-transparent text-slate-500 hover:text-slate-700'
                          }`}
                        >
                          从群组列表选择
                        </button>
                        <button
                          type="button"
                          onClick={() => setCampaignInputMode('manual')}
                          className={`px-4 py-2 text-xs font-bold transition-all border-b-2 -mb-px ${
                            campaignInputMode === 'manual'
                              ? 'border-blue-600 text-blue-600'
                              : 'border-transparent text-slate-500 hover:text-slate-700'
                          }`}
                        >
                          手动输入群组
                        </button>
                      </div>

                      {campaignInputMode === 'library' ? (
                        renderCampaignLibraryPicker()
                      ) : (
                        <div className="flex flex-col gap-1.5 flex-grow">

                          <label className="text-xs font-bold text-slate-600">群组列表 (每行一个，支持公开用户名如 @group 或私密邀请链接)</label>

                          <textarea

                            value={campaignGroupListText}

                            onChange={(e) => setCampaignGroupListText(e.target.value)}

                            placeholder="例：&#10;@group_username&#10;https://t.me/joinchat/AAAAAE...&#10;https://t.me/+invite_hash"

                            className="w-full flex-grow min-h-[200px] bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 resize-none font-mono leading-relaxed"

                          />

                          <p className="text-[10px] text-slate-400">

                            * 多账号安全轰炸会逐个账号确认是否已加入目标群；刚加入的账号本轮不发，避免入群后立刻广告。

                          </p>

                        </div>
                      )}

                    </div>

                  )}



                  {newCampaignAccountId && (
                    <div className="flex-grow flex flex-col gap-4 min-h-[300px]">
                      {/* Input Mode Toggle Tabs */}
                      <div className="flex border-b border-slate-150 mb-2">
                        <button
                          type="button"
                          onClick={() => setCampaignInputMode('folders')}
                          className={`px-4 py-2 text-xs font-bold transition-all border-b-2 -mb-px ${
                            campaignInputMode === 'folders'
                              ? 'border-blue-600 text-blue-600'
                              : 'border-transparent text-slate-500 hover:text-slate-700'
                          }`}
                        >
                          从文件夹选择群组
                        </button>
                        <button
                          type="button"
                          onClick={() => setCampaignInputMode('library')}
                          className={`px-4 py-2 text-xs font-bold transition-all border-b-2 -mb-px ${
                            campaignInputMode === 'library'
                              ? 'border-blue-600 text-blue-600'
                              : 'border-transparent text-slate-500 hover:text-slate-700'
                          }`}
                        >
                          从群组列表选择
                        </button>
                        <button
                          type="button"
                          onClick={() => setCampaignInputMode('manual')}
                          className={`px-4 py-2 text-xs font-bold transition-all border-b-2 -mb-px ${
                            campaignInputMode === 'manual'
                              ? 'border-blue-600 text-blue-600'
                              : 'border-transparent text-slate-500 hover:text-slate-700'
                          }`}
                        >
                          手动输入群组
                        </button>
                      </div>

                      {campaignInputMode === 'library' ? (
                        renderCampaignLibraryPicker()
                      ) : campaignInputMode === 'folders' ? (
                        loadingCampaignFoldersGroups ? (
                          <div className="flex-grow flex flex-col items-center justify-center py-10 text-slate-400 gap-2">
                            <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
                            <span className="text-xs">正在实时读取 Telegram 聊天文件夹...</span>
                          </div>
                        ) : Object.keys(campaignFoldersGroups).length === 0 ? (
                          <div className="flex-grow flex flex-col items-center justify-center py-10 text-slate-400 gap-2">
                            <Database className="w-8 h-8 opacity-30" />
                            <span className="text-xs">该账号在 Telegram 上未同步或未创建任何聊天文件夹。</span>
                          </div>
                        ) : (
                          <div className="flex-grow grid grid-cols-1 md:grid-cols-3 gap-4 overflow-hidden h-[300px]">
                            {/* Folder Selector Sidebar */}
                            <div className="border border-slate-150 rounded-xl p-3 bg-slate-50/50 flex flex-col gap-2 overflow-y-auto">
                              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">根据聊天文件夹全选</span>
                              {Object.keys(campaignFoldersGroups).map(folderName => {
                                const folderGroups = campaignFoldersGroups[folderName];
                                const allIds = folderGroups.map(g => g.chat_id);
                                const isFolderSelected = allIds.length > 0 && allIds.every(id => selectedCampaignGroupIds.includes(id));
                                return (
                                  <button
                                    key={folderName}
                                    type="button"
                                    onClick={() => {
                                      const nextIds = [...selectedCampaignGroupIds];
                                      if (isFolderSelected) {
                                        setSelectedCampaignGroupIds(nextIds.filter(id => !allIds.includes(id)));
                                      } else {
                                        allIds.forEach(id => {
                                          if (!nextIds.includes(id)) {
                                            nextIds.push(id);
                                          }
                                        });
                                        setSelectedCampaignGroupIds(nextIds);
                                      }
                                    }}
                                    className={`flex items-center justify-between px-3 py-2 rounded-lg text-left text-xs font-semibold transition-all ${
                                      isFolderSelected
                                        ? 'bg-blue-50 text-blue-600 border border-blue-100/50'
                                        : 'bg-white hover:bg-slate-50 text-slate-700 border border-slate-100'
                                    }`}
                                  >
                                    <span>{folderName}</span>
                                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                                      isFolderSelected
                                        ? 'bg-blue-100 text-blue-700'
                                        : 'bg-slate-100 text-slate-500'
                                    }`}>{folderGroups.length}</span>
                                  </button>
                                );
                              })}
                            </div>

                            {/* Groups list of first folder or selected */}
                            <div className="md:col-span-2 border border-slate-150 rounded-xl bg-slate-50/20 flex flex-col overflow-hidden">
                              <div className="bg-slate-50/80 px-3 py-2 border-b border-slate-150 flex items-center justify-between shrink-0">
                                <span className="text-[10px] font-bold text-slate-500">已选中 {selectedCampaignGroupIds.length} 个群组</span>
                                <div className="flex gap-2">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      // Select all unique groups
                                      const allUniqueIds: number[] = [];
                                      Object.keys(campaignFoldersGroups).forEach(f => {
                                        campaignFoldersGroups[f].forEach(g => {
                                          if (!allUniqueIds.includes(g.chat_id)) {
                                            allUniqueIds.push(g.chat_id);
                                          }
                                        });
                                      });
                                      setSelectedCampaignGroupIds(allUniqueIds);
                                    }}
                                    className="text-[10px] text-blue-600 hover:text-blue-700 font-semibold"
                                  >
                                    全选所有
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setSelectedCampaignGroupIds([])}
                                    className="text-[10px] text-slate-500 hover:text-slate-600"
                                  >
                                    清除
                                  </button>
                                </div>
                              </div>

                              <div className="flex-grow overflow-y-auto p-2.5 flex flex-col gap-1.5">
                                {(() => {
                                  const uniqueGroups: Array<{ chat_id: number; title: string; username: string; folder?: string }> = [];
                                  const sortedFolders = Object.keys(campaignFoldersGroups).sort((a, b) => {
                                    const aVirtual = a === '所有群组' || a === '非文件夹群组';
                                    const bVirtual = b === '所有群组' || b === '非文件夹群组';
                                    if (aVirtual && !bVirtual) return 1;
                                    if (!aVirtual && bVirtual) return -1;
                                    return 0;
                                  });
                                  sortedFolders.forEach(folder => {
                                    campaignFoldersGroups[folder].forEach(g => {
                                      if (!uniqueGroups.some(ug => ug.chat_id === g.chat_id)) {
                                        uniqueGroups.push({ ...g, folder });
                                      }
                                    });
                                  });

                                  return uniqueGroups.map(g => {
                                    const isSelected = selectedCampaignGroupIds.includes(g.chat_id);
                                    return (
                                      <label
                                        key={g.chat_id}
                                        className={`flex items-center justify-between p-2 rounded-lg border text-xs cursor-pointer select-none transition-colors ${
                                          isSelected
                                            ? 'bg-blue-50/30 border-blue-100 text-blue-900 font-medium'
                                            : 'bg-white border-slate-100 hover:bg-slate-50/50 text-slate-700'
                                        }`}
                                      >
                                        <div className="flex items-center gap-2.5 truncate max-w-[80%]">
                                          <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={(e) => {
                                              if (e.target.checked) {
                                                setSelectedCampaignGroupIds(prev => [...prev, g.chat_id]);
                                              } else {
                                                setSelectedCampaignGroupIds(prev => prev.filter(id => id !== g.chat_id));
                                              }
                                            }}
                                            className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-3.5 h-3.5"
                                          />
                                          <div className="flex flex-col gap-0.5 truncate">
                                            <span className="font-semibold truncate">{g.title}</span>
                                            {g.username && <span className="text-[10px] text-slate-400 font-mono truncate">@{g.username}</span>}
                                          </div>
                                        </div>
                                        <span className="text-[9px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-md font-mono shrink-0 ml-1">
                                          {g.folder}
                                        </span>
                                      </label>
                                    );
                                  });
                                })()}
                              </div>
                            </div>
                          </div>
                        )
                      ) : (
                        <div className="flex flex-col gap-1.5 flex-grow">
                          <label className="text-xs font-bold text-slate-600">群组列表 (每行一个，支持公开用户名如 @group 或私密邀请链接)</label>
                          <textarea
                            value={campaignGroupListText}
                            onChange={(e) => setCampaignGroupListText(e.target.value)}
                            placeholder="例：&#10;@group_username&#10;https://t.me/joinchat/AAAAAE...&#10;https://t.me/+invite_hash"
                            className="w-full flex-grow min-h-[200px] bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 resize-none font-mono leading-relaxed"
                          />
                          <p className="text-[10px] text-slate-400">
                            * 请在此处逐行输入需要发送的群组用户名或链接。
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                </div>



                {/* Right Column: Parameters and Message */}

                <div className="flex flex-col gap-5 bg-white border border-slate-150 rounded-2xl p-5 shadow-xs">

                  <span className="text-xs font-bold text-slate-700 border-b border-slate-100 pb-2">轰炸执行参数</span>

                  

                  <div className="grid grid-cols-2 gap-3.5">

                    <div className="flex flex-col gap-1.5">

                      <label className="text-[11px] font-bold text-slate-600">循环次数 (不填为一直执行)</label>

                      <input

                        type="number"

                        min="0"

                        value={campaignMaxCycles === 0 ? '' : campaignMaxCycles}

                        onChange={(e) => { const val = e.target.value; setCampaignMaxCycles(val === '' ? '' : parseInt(val) || 0); }}

                        placeholder="一直运行"

                        className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono"

                      />

                    </div>

                    <div className="flex flex-col gap-1.5">

                      <label className="text-[11px] font-bold text-slate-600">每轮循环间隔 (分钟)</label>

                      <input

                        type="number"

                        min="1"

                        value={campaignRoundInterval}

                        onChange={(e) => { const val = e.target.value; setCampaignRoundInterval(val === '' ? '' : parseInt(val) || 0); }}

                        className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono"

                      />

                    </div>

                  </div>



                  <div className="flex flex-col gap-2">

                    <div className="flex justify-between items-center">

                      <label className="text-[11px] font-bold text-slate-600">单个群发送间隔 (秒)</label>

                      <label className="flex items-center gap-1 text-[10px] text-slate-500 cursor-pointer select-none">

                        <input

                          type="checkbox"

                          checked={campaignIsSafety}

                          onChange={(e) => setCampaignIsSafety(e.target.checked)}

                          className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-3 h-3"

                        />

                        <span>🛡️ 安全随机模式</span>

                      </label>

                    </div>

                    <input

                      type="number"

                      min="5"

                      value={campaignGroupInterval}

                      onChange={(e) => { const val = e.target.value; setCampaignGroupInterval(val === '' ? '' : parseInt(val) || 0); }}

                      className={`w-full bg-slate-50 border rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono ${

                        (campaignGroupInterval !== '' && Number(campaignGroupInterval) < 5) ? 'border-rose-400 focus:ring-rose-500/20 focus:border-rose-500' : 'border-slate-200'

                      }`}

                    />

                    {campaignGroupInterval !== '' && Number(campaignGroupInterval) < 5 && (

                      <span className="text-[9px] text-rose-600 font-medium leading-none">间隔值不可小于 5 秒，否则可能触发风控</span>

                    )}

                    {campaignIsSafety && (

                      <span className="text-[9px] text-slate-400 font-light italic">

                        * 每个群发送的真实延迟将在 5 秒到 {campaignGroupInterval} 秒之间随机波动。

                      </span>

                    )}

                  </div>



                  <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50/60 p-3.5">

                    <label className="flex items-start gap-2 text-xs text-slate-700 cursor-pointer select-none">

                      <input

                        type="checkbox"

                        checked={campaignMultiAccountSafety}

                        onChange={(e) => setCampaignMultiAccountSafety(e.target.checked)}

                        disabled={selectedCampaignAccountIds.length <= 1}

                        className="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-3.5 h-3.5 disabled:opacity-40"

                      />

                      <span className="flex flex-col gap-1">

                        <span className="font-bold text-slate-700 flex items-center gap-1">

                          <Shield className="w-3.5 h-3.5 text-blue-500" />

                          启用多账号安全轰炸

                        </span>

                        <span className="text-[10px] text-slate-400 leading-relaxed">

                          开启后，每次发送前由系统自动从可用账号池挑选更合适的账号，并自动分散连续发送与限流风险。未开启时，多账号按普通轮询执行。

                        </span>

                      </span>

                    </label>

                    {selectedCampaignAccountIds.length <= 1 && (

                      <span className="text-[9px] text-amber-600 font-medium">选择 2 个及以上账号后可启用该策略。</span>

                    )}

                    {campaignMultiAccountSafety && selectedCampaignAccountIds.length > 1 && (

                      <div className="rounded-lg border border-blue-100 bg-white/80 p-3 text-[10px] text-slate-500 leading-relaxed">

                        策略说明：系统会综合账号池数量、群发送间隔、最近使用次数和限流状态，自动随机选择执行账号。账号发送后会进入动态短冷却；如果全部账号都在冷却，系统会选择最接近释放且使用次数较少的账号继续执行，避免任务因为参数过死而无人可用。

                      </div>

                    )}

                  </div>

                  <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50/60 p-3.5">

                    <label className="flex items-start gap-2 text-xs text-slate-700 cursor-pointer select-none">

                      <input

                        type="checkbox"

                        checked={campaignStrategyEnabled}

                        onChange={(e) => setCampaignStrategyEnabled(e.target.checked)}

                        className="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-3.5 h-3.5"

                      />

                      <span className="flex flex-col gap-1">

                        <span className="font-bold text-slate-700 flex items-center gap-1">

                          <span>⚡</span>

                          启用智能策略轰炸模式

                        </span>

                        <span className="text-[10px] text-slate-400 leading-relaxed">

                          开启后，系统在发送前自动检测群组分类（中文长/短、英文长/短），随机匹配该分类下的广告模板词，避免广告语长度或语种错配。

                        </span>

                      </span>

                    </label>

                  </div>



                  {campaignStrategyEnabled ? (

                    <div className="rounded-xl border border-amber-100 bg-amber-50/30 p-4 flex flex-col gap-2">

                      <span className="text-xs font-bold text-amber-800 flex items-center gap-1.5">

                        <span>💡</span> 智能策略投递已生效

                      </span>

                      <p className="text-[11px] text-amber-700 leading-relaxed">

                        系统将自动根据目标群组分类（<b>中文长</b>、<b>中文短</b>、<b>英文长</b>、<b>英文短</b>）匹配您在“常用广告语”中录入的模板，并随机挑选一条发送。

                      </p>

                      <p className="text-[11px] text-amber-600/80 font-medium italic">

                        * 请确保已录入对应分类的广告文本，否则将使用普通输入内容或安全兜底模板。

                      </p>

                    </div>

                  ) : (
<div className="flex flex-col gap-1.5">

                    <div className="flex justify-between items-center mb-1">

                      <label className="text-[11px] font-bold text-slate-600">轰炸内容 (广告词)</label>

                      <div className="flex items-center gap-2">

                        <button

                          type="button"

                          onClick={() => setActiveTab('templates')}

                          className="text-[10px] text-blue-600 hover:text-blue-700 font-semibold flex items-center gap-0.5"

                        >

                          ⚙️ 管理预设

                        </button>

                      </div>

                    </div>

                    {adTemplates.length > 0 && (
                      <div className="mb-3 bg-slate-50 border border-slate-150 rounded-xl p-3 flex flex-col gap-3">
                        
                        {/* 1. 分类 Tab 过滤栏 (精致药丸分段设计) */}
                        <div className="grid grid-cols-2 min-[420px]:grid-cols-3 gap-1.5 bg-slate-100 p-1 rounded-lg">
                          {(["全部", "中文长", "中文短", "英文长", "英文短"] as const).map(tab => {
                            const count = tab === '全部' 
                              ? adTemplates.length 
                              : adTemplates.filter(ad => ad.group_type === tab).length;
                            const isSelected = selectedAdFilter === tab;
                            return (
                              <button
                                key={tab}
                                type="button"
                                onClick={() => setSelectedAdFilter(tab)}
                                className={`text-[10px] px-2.5 py-1 rounded-md font-bold transition-all flex items-center justify-between gap-1 min-w-0 ${
                                  isSelected
                                    ? 'bg-white text-slate-800 shadow-xs'
                                    : 'text-slate-500 hover:text-slate-800 hover:bg-white/40'
                                }`}
                              >
                                <span className="truncate">{tab}</span>
                                <span className={`text-[9px] px-1 py-0.2 rounded-full shrink-0 ${
                                  isSelected ? 'bg-slate-100 text-slate-600' : 'bg-slate-200/60 text-slate-500'
                                }`}>
                                  {count}
                                </span>
                              </button>
                            );
                          })}
                        </div>

                        {/* 2. 精致微型操作栏 (防挤压单行布局) */}
                        <div className="flex justify-between items-center text-[10px] px-0.5">
                          <span className="font-bold text-slate-500">
                            已选 <span className="text-blue-600 font-extrabold">{selectedAdTemplateIds.length}</span> / {adTemplates.length} 条广告语
                          </span>
                          <div className="flex items-center gap-2.5">
                            <button
                              type="button"
                              onClick={() => {
                                const currentFilteredIds = adTemplates
                                  .filter(ad => selectedAdFilter === '全部' ? true : ad.group_type === selectedAdFilter)
                                  .map(ad => ad.id);
                                const allCurrentSelected = currentFilteredIds.every(id => selectedAdTemplateIds.includes(id));
                                if (allCurrentSelected) {
                                  setSelectedAdTemplateIds(prev => prev.filter(id => !currentFilteredIds.includes(id)));
                                } else {
                                  setSelectedAdTemplateIds(prev => Array.from(new Set([...prev, ...currentFilteredIds])));
                                }
                              }}
                              className="text-blue-600 hover:text-blue-700 font-bold"
                            >
                              全选当前分类
                            </button>
                            <span className="text-slate-200">|</span>
                            <button
                              type="button"
                              onClick={() => setSelectedAdTemplateIds([])}
                              className="text-slate-500 hover:text-rose-600 font-bold"
                            >
                              清除全部已选
                            </button>
                          </div>
                        </div>

                        {/* 3. 过滤后的流式单列列表 (彻底解决两列重叠遮挡问题) */}
                        <div className="flex flex-col gap-1.5 max-h-32 overflow-y-auto pr-0.5">
                          {adTemplates
                            .filter(ad => selectedAdFilter === '全部' ? true : ad.group_type === selectedAdFilter)
                            .map(ad => {
                              const isChecked = selectedAdTemplateIds.includes(ad.id);
                              return (
                                <label 
                                  key={ad.id} 
                                  className={`flex items-center gap-3 p-2 rounded-lg border cursor-pointer transition-all ${
                                    isChecked
                                      ? 'bg-blue-50/40 border-blue-200 text-blue-900 shadow-2xs'
                                      : 'bg-white border-slate-150 hover:border-slate-200 text-slate-700'
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={isChecked}
                                    onChange={(e) => {
                                      if (e.target.checked) {
                                        setSelectedAdTemplateIds(prev => [...prev, ad.id]);
                                      } else {
                                        setSelectedAdTemplateIds(prev => prev.filter(id => id !== ad.id));
                                      }
                                    }}
                                    className="rounded text-blue-600 focus:ring-blue-500/20 w-3.5 h-3.5"
                                  />
                                  <div className="flex-1 min-w-0 flex flex-col gap-0.5">
                                    <div className="flex items-center justify-between gap-2">
                                      <span className="font-bold text-[10px] text-slate-800 truncate" title={ad.description}>
                                        {ad.description}
                                      </span>
                                      <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded border shrink-0 ${
                                        ad.group_type?.includes('长')
                                          ? 'bg-purple-50 text-purple-600 border-purple-100/60'
                                          : 'bg-indigo-50 text-indigo-600 border-indigo-100/60'
                                      }`}>
                                        {ad.group_type}
                                      </span>
                                    </div>
                                    <span className="text-slate-400 text-[10px] truncate" title={ad.content}>
                                      {ad.content}
                                    </span>
                                  </div>
                                </label>
                              );
                            })}
                          {adTemplates.filter(ad => selectedAdFilter === '全部' ? true : ad.group_type === selectedAdFilter).length === 0 && (
                            <div className="text-center text-slate-400 text-[10px] py-4 bg-white rounded-lg border border-dashed border-slate-200">
                              该分类下暂无广告语
                            </div>
                          )}
                        </div>

                      </div>
                    )}

                    <textarea

                      value={campaignMessage}

                      onChange={(e) => setCampaignMessage(e.target.value)}

                      placeholder="请输入您的广告推广信息文本，支持 Telegram 的 HTML 排版标记（如 <b>, <i>, <a> 等）。支持使用 '====' 分隔多个不同的广告词进行随机轰炸..."

                      className="w-full h-36 bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 resize-none font-medium leading-relaxed"

                    ></textarea>

                  </div>
                  )}

                </div>



              </div>



              {/* Modal Footer */}

              <div className="p-5 border-t border-slate-100 flex justify-end gap-3 bg-slate-50/50">

                <button

                  onClick={() => setShowCreateCampaignModal(false)}

                  className="px-5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-all"

                >

                  取消

                </button>

                <button

                  onClick={handleCreateCampaignTask}

                  disabled={

                    selectedCampaignAccountIds.length === 0 ||

                    (!campaignStrategyEnabled && selectedAdTemplateIds.length === 0 && !campaignMessage.trim()) ||

                    (campaignInputMode === 'library' && selectedCampaignLibraryGroupIds.length === 0) ||

                    (selectedCampaignAccountIds.length === 1 && campaignInputMode === 'folders' && selectedCampaignGroupIds.length === 0) ||

                    (campaignInputMode === 'manual' && !campaignGroupListText.trim())

                  }

                  className="px-6 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 active:scale-95 rounded-lg transition-all shadow-sm flex items-center gap-1.5"

                >

                  <Play className="w-3.5 h-3.5" />

                  <span>启动群发广告</span>

                </button>

              </div>



            </div>

          </div>

        )}



        {/* K. CAMPAIGN LOGS & STATUS DETAILS MODAL */}

        {showCampaignLogsModal && activeCampaignTaskId && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-4xl flex flex-col max-h-[85vh] overflow-hidden">

              

              {/* Modal Header */}

              {(() => {

                const groupedTasks = groupCampaignTasks(campaignTasks);

                const task = groupedTasks.find(t => t.task_ids.includes(activeCampaignTaskId || ''));

                if (!task) return null;

                const totalSent = task.success_count + task.fail_count;

                const successRate = totalSent > 0 ? Math.round((task.success_count / totalSent) * 100) : 100;

                let targetGroupsList = [];

                try {

                  targetGroupsList = JSON.parse(task.target_groups_json);

                } catch (e) {}

                

                return (

                  <>

                    <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                      <div>

                        <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">

                          <span>📊 任务发送日志与监控面板</span>

                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${

                            task.status === 'running' 

                              ? 'bg-emerald-50 text-emerald-700 border-emerald-100'

                              : task.status === 'completed'

                              ? 'bg-blue-50 text-blue-700 border-blue-100'

                              : task.status === 'stopped'

                              ? 'bg-slate-50 text-slate-600 border-slate-200'

                              : 'bg-rose-50 text-rose-700 border-rose-100'

                          }`}>

                            {task.status === 'running' && '运行中'}

                            {task.status === 'completed' && '已完成'}

                            {task.status === 'stopped' && '已停止'}

                            {task.status === 'failed' && '执行出错'}

                          </span>

                        </h3>

                        <p className="text-xs text-slate-400 mt-0.5 font-light font-mono">

                          执行账号: {task.phones.join(', ')} | 创建时间: {task.created_at}

                        </p>

                      </div>

                      <div className="flex items-center gap-2">

                        <button

                          onClick={() => fetchCampaignTaskLogs(activeCampaignTaskId)}

                          className="p-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5"

                          title="刷新日志"

                        >

                          <RefreshCw className="w-3.5 h-3.5" />

                        </button>

                        <button 

                          onClick={() => {

                            setShowCampaignLogsModal(false);

                            setActiveCampaignTaskId(null);

                            setActiveCampaignTaskLogs([]);

                          }}

                          className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                        >

                          <X className="w-5 h-5" />

                        </button>

                      </div>

                    </div>



                    {/* Modal Body */}

                    <div className="p-6 overflow-y-auto flex-grow bg-slate-50/20 flex flex-col gap-6">

                      {/* Stats Overview Rows */}

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">

                        <div className="bg-white border border-slate-100 rounded-xl p-4 shadow-xs text-center">

                          <span className="text-[10px] text-slate-400 font-bold block">发送轮数</span>

                          <span className="text-lg font-bold text-slate-800 font-mono mt-1 block">

                            {task.max_cycles === 0 ? `第 ${task.current_cycle} 轮 (无限)` : `第 ${task.current_cycle} / ${task.max_cycles} 轮`}

                          </span>

                        </div>

                        <div className="bg-white border border-slate-100 rounded-xl p-4 shadow-xs text-center">

                          <span className="text-[10px] text-emerald-500 font-bold block">成功发送数量</span>

                          <span className="text-lg font-bold text-emerald-600 font-mono mt-1 block">

                            {task.success_count}

                          </span>

                        </div>

                        <div className="bg-white border border-slate-100 rounded-xl p-4 shadow-xs text-center">

                          <span className="text-[10px] text-rose-500 font-bold block">失败发送数量</span>

                          <span className="text-lg font-bold text-rose-600 font-mono mt-1 block">

                            {task.fail_count}

                          </span>

                        </div>

                        <div className="bg-white border border-slate-100 rounded-xl p-4 shadow-xs text-center">

                          <span className="text-[10px] text-blue-500 font-bold block">本次发送成功率</span>

                          <span className="text-lg font-bold text-blue-600 font-mono mt-1 block">

                            {successRate}%

                          </span>

                        </div>

                      </div>



                      {/* Message preview details */}

                      <div className="bg-white border border-slate-150 rounded-xl p-4 shadow-xs flex flex-col gap-1.5">

                        <span className="text-xs font-bold text-slate-700">📜 营销广告词文本</span>

                        <div className="bg-slate-50 rounded-xl p-3 text-xs text-slate-600 font-medium max-h-24 overflow-y-auto whitespace-pre-wrap leading-relaxed select-all">

                          {task.message}

                        </div>

                      </div>



                      {/* Real-time sending logs list */}

                      <div className="flex-grow flex flex-col gap-2 min-h-[250px]">

                        <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">

                          🖥️ 单次群发投递流水明细

                        </span>

                        

                        <div className="border border-slate-150 rounded-xl overflow-hidden bg-white shadow-sm flex-grow overflow-y-auto max-h-[300px]">

                          {activeCampaignTaskLogs.length === 0 ? (

                            <div className="text-center py-12 text-xs text-slate-400">暂无该任务的群发日志明细。</div>

                          ) : (

                            <table className="w-full text-left border-collapse table-fixed">

                              <thead>

                                <tr className="border-b border-slate-100 bg-slate-50/50 text-[10px] font-bold uppercase text-slate-500 tracking-wider">

                                  <th className="py-2.5 px-4 w-[20%]">投递时间</th>

                                  <th className="py-2.5 px-4 w-[15%]">执行账号</th>

                                  <th className="py-2.5 px-4 w-[10%] text-center">轮次</th>

                                  <th className="py-2.5 px-4 w-[25%]">目标群组标题</th>

                                  <th className="py-2.5 px-4 w-[12%] text-center">状态</th>

                                  <th className="py-2.5 px-4 w-[18%]">流水详情</th>

                                </tr>

                              </thead>

                                {activeCampaignTaskLogs.map((log) => {
                                  let username = "";
                                  try {
                                    const targetGroups = JSON.parse(task.target_groups_json || "[]");
                                    const matched = targetGroups.find((g: any) => 
                                      String(g.chat_id) === String(log.group_id) || 
                                      String(g.chat_id).replace(/^-100/, '') === String(log.group_id).replace(/^-100/, '')
                                    );
                                    if (matched && matched.username) {
                                      username = matched.username;
                                    }
                                  } catch (e) {}

                                  const showToast = (msg: string) => {
                                    const toast = document.createElement("div");
                                    toast.className = "fixed bottom-8 right-8 bg-slate-900/90 text-white text-xs px-4 py-2.5 rounded-xl shadow-xl z-[9999] transition-all duration-300 opacity-0 transform translate-y-2 backdrop-blur-xs font-sans font-medium flex items-center gap-1.5 border border-white/10";
                                    toast.innerHTML = `<span>📋</span> ${msg}`;
                                    document.body.appendChild(toast);
                                    setTimeout(() => {
                                      toast.classList.remove("opacity-0", "translate-y-2");
                                      toast.classList.add("opacity-100", "translate-y-0");
                                    }, 10);
                                    setTimeout(() => {
                                      toast.classList.remove("opacity-100", "translate-y-0");
                                      toast.classList.add("opacity-0", "translate-y-2");
                                      setTimeout(() => toast.remove(), 300);
                                    }, 2000);
                                  };

                                  const handleCopy = () => {
                                    const copyText = username || log.group_id;
                                    if (!copyText) return;
                                    navigator.clipboard.writeText(copyText).then(() => {
                                      showToast(`已成功复制: ${copyText}`);
                                    }).catch((err) => {
                                      console.error("Copy failed: ", err);
                                    });
                                  };

                                  let displayDetail = log.detail;
                                  let tooltipDetail = log.detail;
                                  if (log.status === 'success') {
                                    const previewMatch = log.detail.match(/\[预览:\s*([\s\S]+)\]$/);
                                    if (previewMatch) {
                                      const text = previewMatch[1];
                                      displayDetail = text.length > 25 ? text.slice(0, 25) + "..." : text;
                                      tooltipDetail = text;
                                    } else {
                                      displayDetail = "消息发送成功";
                                      tooltipDetail = log.detail;
                                    }
                                  } else {
                                    displayDetail = log.detail;
                                    tooltipDetail = log.detail;
                                  }

                                  return (
                                    <tr key={log.id} className="hover:bg-slate-50/50 transition-colors">
                                      <td className="py-2.5 px-4 text-slate-500 font-mono text-[10px] truncate" title={log.timestamp}>
                                        {log.timestamp}
                                      </td>
                                      <td className="py-2.5 px-4 text-slate-600 font-mono text-[11px] truncate" title={log.phone}>
                                        {log.phone || '-'}
                                      </td>
                                      <td className="py-2.5 px-4 text-center font-bold text-slate-600 text-[11px]">
                                        {log.cycle}
                                      </td>
                                      <td 
                                        className={`py-2.5 px-4 text-slate-800 font-semibold text-[11px] truncate ${username ? 'cursor-pointer hover:underline hover:text-indigo-600' : ''}`}
                                        title={username ? `点击复制群用户名: ${username}` : `群ID: ${log.group_id}`}
                                        onClick={handleCopy}
                                      >
                                        {log.group_title} <span className="text-[10px] text-slate-400 font-light font-mono">({log.group_id})</span>
                                      </td>
                                      <td className="py-2.5 px-4 text-center">
                                        {log.status === 'success' ? (
                                          <span className="px-2 py-0.5 bg-emerald-50 text-emerald-600 border border-emerald-100 rounded text-[10px] font-bold">
                                            成功
                                          </span>
                                        ) : log.status === 'skipped' ? (
                                          <span className="px-2 py-0.5 bg-amber-50 text-amber-600 border border-amber-100 rounded text-[10px] font-bold">
                                            跳过
                                          </span>
                                        ) : (
                                          <span className="px-2 py-0.5 bg-rose-50 text-rose-600 border border-rose-100 rounded text-[10px] font-bold">
                                            失败
                                          </span>
                                        )}
                                      </td>
                                      <td className="py-2.5 px-4 text-slate-500 font-mono text-[10px] truncate" title={tooltipDetail}>
                                        {displayDetail}
                                      </td>
                                    </tr>
                                  );
                                })}

                            </table>

                          )}

                        </div>

                      </div>



                    </div>

                  </>

                );

              })()}



              {/* Modal Footer */}

              <div className="p-5 border-t border-slate-100 flex justify-end bg-slate-50/35">

                <button 

                  onClick={() => {

                    setShowCampaignLogsModal(false);

                    setActiveCampaignTaskId(null);

                    setActiveCampaignTaskLogs([]);

                  }}

                  className="px-6 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-lg transition-all"

                >

                  关闭

                </button>

              </div>



            </div>

          </div>

        )}



        {/* H. INVALID GROUPS CLEANUP REMINDER MODAL */}
        {showInvalidGroupsModal && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col max-h-[85vh] overflow-hidden">
              
              {/* Modal Header */}
              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <div>
                  <h3 className="font-bold text-slate-900 text-base">🚫 检测到无效限制群组</h3>
                  <p className="text-xs text-slate-400 mt-0.5 font-light">
                    本次加群任务中，有 {invalidGroupsToDelete.length} 个群组已被屏蔽或失效
                  </p>
                </div>
                <button 
                  onClick={() => {
                    setShowInvalidGroupsModal(false);
                    setInvalidGroupsToDelete([]);
                  }}
                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6 overflow-y-auto flex flex-col gap-4">
                <p className="text-xs text-slate-600 leading-relaxed">
                  以下群组在加群时返回了“版权受限/无效/已屏蔽”的状态。你是否需要将它们从<strong>群组列表</strong>中批量删除？
                </p>
                
                <div className="border border-slate-100 rounded-xl overflow-hidden max-h-40 overflow-y-auto bg-slate-50/50 p-2 flex flex-col gap-2">
                  {invalidGroupsToDelete.map((g, idx) => (
                    <div key={idx} className="flex justify-between items-center text-xs p-2 bg-white rounded-lg border border-slate-100 shadow-xs">
                      <div className="flex flex-col gap-0.5 truncate max-w-[70%]">
                        <span className="font-semibold text-slate-800 truncate">{g.title || '未命名群组'}</span>
                        <span className="font-mono text-slate-400 truncate text-[10px]">{g.link}</span>
                      </div>
                      <span className="text-[10px] text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded border border-purple-100 font-medium">版权屏蔽/无效</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Modal Footer */}
              <div className="p-5 border-t border-slate-100 flex justify-end gap-3 bg-slate-50/50">
                <button
                  onClick={() => {
                    setShowInvalidGroupsModal(false);
                    setInvalidGroupsToDelete([]);
                  }}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-all"
                >
                  保留在列表中
                </button>
                <button
                  onClick={async () => {
                    const backendUrl = BASE_URL;
                    try {
                      const ids = invalidGroupsToDelete.map(g => g.id);
                      const res = await fetch(`${backendUrl}/api/groups/batch-delete`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ids })
                      });
                      if (res.ok) {
                        setToastText(`已成功删除 ${ids.length} 个无效群组！`);
                        setTimeout(() => setToastText(''), 3000);
                        fetchGroups();
                      } else {
                        const data = await res.json();
                        alert(`删除失败: ${data.detail || '原因未知'}`);
                      }
                    } catch (e: any) {
                      alert(`请求失败: ${e.message}`);
                    }
                    setShowInvalidGroupsModal(false);
                    setInvalidGroupsToDelete([]);
                  }}
                  className="px-4 py-2 text-xs font-semibold text-white bg-purple-600 hover:bg-purple-700 active:scale-95 rounded-lg transition-all shadow-sm"
                >
                  批量删除无效群组
                </button>
              </div>

            </div>
          </div>
        )}


        {showBotNodeModal && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
            <div className={`bg-white rounded-3xl border border-slate-100 shadow-xl w-full flex flex-col overflow-hidden animate-scale-in transition-all duration-300 ${editingBotNode ? 'max-w-5xl' : 'max-w-md'}`}>
              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <div>
                  <h3 className="font-bold text-slate-900 text-base">{editingBotNode ? `⚙️ ${botNodeTitle || editingBotNode.title} 详情与专属授权管理` : '🤖 新增电报 Bot 节点'}</h3>
                  <p className="text-xs text-slate-400 mt-0.5">{editingBotNode ? '配置 Bot 连接参数，并手动增删该 Bot 专属的电报账号与中转群授权' : '配置注册在 BotFather 里的 Token 和基本服务属性'}</p>
                </div>
                <button onClick={() => setShowBotNodeModal(false)} className="text-slate-400 hover:text-slate-600 transition-colors"><X className="w-5 h-5" /></button>
              </div>
              <div className={`grid grid-cols-1 ${editingBotNode ? 'md:grid-cols-3' : 'grid-cols-1'} divide-y md:divide-y-0 md:divide-x divide-slate-100 overflow-y-auto max-h-[85vh]`}>
                <div className="p-6 flex flex-col gap-4 col-span-1">
                  <h4 className="font-bold text-slate-850 text-xs border-b border-slate-50 pb-2 flex items-center gap-1">🛠️ 节点基础配置</h4>
                  <form onSubmit={saveBotNode} className="flex flex-col gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-bold text-slate-600">Bot 节点名称</label>
                      <input type="text" required value={botNodeTitle} onChange={(e) => setBotNodeTitle(e.target.value)} placeholder="例如: 财务通知助手" className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-xs font-medium placeholder-slate-300" />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-bold text-slate-600">Bot 用户名 (Username)</label>
                      <input type="text" required value={botNodeUsername} onChange={(e) => setBotNodeUsername(e.target.value)} placeholder="例如: RosePayTest_bot" className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-xs font-medium placeholder-slate-300" />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-bold text-slate-600">Bot Token (BotFather 申请值)</label>
                      <input type="password" required value={botNodeToken} onChange={(e) => setBotNodeToken(e.target.value)} placeholder="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ" className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-xs font-medium placeholder-slate-300 font-mono" />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-bold text-slate-600">Bot 服务类型</label>
                      <select value={botNodeType} onChange={(e) => setBotNodeType(e.target.value)} className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-xs font-medium bg-white">
                        <option value="ai_bot">AI 控制助手 (ai_bot)</option>
                        <option value="translate_bot">翻译助手 (translate_bot)</option>
                        <option value="custom">自定义业务 Bot (custom)</option>
                      </select>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-bold text-slate-600">Bot 功能描述</label>
                      <textarea value={botNodeDescription} onChange={(e) => setBotNodeDescription(e.target.value)} placeholder="简要说明此 Bot 在平台内的业务用途..." rows={2} className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-xs font-medium placeholder-slate-300 resize-none" />
                    </div>
                    <div className="flex items-center gap-2 py-1">
                      <input type="checkbox" id="formBotActiveCheck" checked={botNodeActive === 1} onChange={(e) => setBotNodeActive(e.target.checked ? 1 : 0)} className="w-4 h-4 text-blue-600 rounded-sm border-slate-300 focus:ring-blue-500" />
                      <label htmlFor="formBotActiveCheck" className="text-xs font-bold text-slate-700 cursor-pointer select-none">启用此 Bot 节点</label>
                    </div>
                    <div className="flex gap-3 mt-4 border-t border-slate-50 pt-4">
                      {editingBotNode && <button type="button" onClick={() => deleteBotNode(editingBotNode)} className="px-3 py-2.5 border border-rose-200 text-rose-600 hover:bg-rose-50 rounded-xl font-bold text-xs transition-colors">删除</button>}
                      <button type="button" onClick={() => setShowBotNodeModal(false)} className="flex-1 px-3 py-2.5 border border-slate-200 hover:bg-slate-50 rounded-xl font-bold text-xs text-slate-600 transition-colors">取消</button>
                      <button type="submit" className="flex-1 px-3 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-xs shadow-md transition-all active:scale-[0.98]">保存</button>
                    </div>
                  </form>
                </div>

                {editingBotNode && (
                  <div className="p-6 flex flex-col gap-4 col-span-2 bg-slate-50/25">
                    <div className="flex border-b border-slate-100 pb-1.5 gap-2">
                      <button type="button" onClick={() => setBotManageTab('auth')} className={`px-4 py-2 text-xs font-black rounded-xl transition-all ${botManageTab === 'auth' ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-400 hover:text-slate-700'}`}>
                        {isTranslateBotType(editingBotNode.bot_type) ? '🔑 绑定账号情况' : '🔑 专属授权账号与中转群'}
                      </button>
                      {!isTranslateBotType(editingBotNode.bot_type) && (
                        <button type="button" onClick={() => setBotManageTab('reply')} className={`px-4 py-2 text-xs font-black rounded-xl transition-all ${botManageTab === 'reply' ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-400 hover:text-slate-700'}`}>💬 首问随机自动回复模板</button>
                      )}
                    </div>

                    {botManageTab === 'auth' && (
                      <div className="flex flex-col gap-4 animate-fade-in">
                        <div className="flex justify-between items-center">
                          <span className="text-[10px] text-slate-400 font-bold">
                            {isTranslateBotType(editingBotNode.bot_type) ? '查看翻译助手当前绑定的电报账号' : '管理此 Bot 的访问权限与消息接收群组'}
                          </span>
                          {!isTranslateBotType(editingBotNode.bot_type) && (
                            <button type="button" onClick={openCreateBotAuthModal} className="px-2.5 py-1 bg-slate-950 text-white hover:bg-slate-800 rounded-lg text-[10px] font-black transition-all active:scale-[0.97]">➕ 免注册手动新增授权</button>
                          )}
                        </div>
                        <div className="bg-white border border-slate-100 rounded-2xl overflow-hidden shadow-xs">
                          <table className="w-full text-left border-collapse text-xs">
                            <thead>
                              <tr className="bg-slate-50/70 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                                <th className="py-3 px-4">{isTranslateBotType(editingBotNode.bot_type) ? '绑定电报账号' : '电报用户 / 群组'}</th>
                                <th className="py-3 px-4">Chat ID</th>
                                <th className="py-3 px-4">角色权限</th>
                                <th className="py-3 px-4">归属绑定账号</th>
                                {!isTranslateBotType(editingBotNode.bot_type) && <th className="py-3 px-4 text-right">操作</th>}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-50">
                              {botAuthorizations.length === 0 ? (
                                <tr><td colSpan={isTranslateBotType(editingBotNode.bot_type) ? 4 : 5} className="py-8 text-center text-xs text-slate-400 bg-white">📭 该 Bot 暂无任何专属授权记录。</td></tr>
                              ) : botAuthorizations.map((auth, idx) => (
                                <tr key={`${auth.bot_type}-${auth.telegram_chat_id}-${idx}`} className="hover:bg-slate-50/50 transition-colors">
                                  <td className="py-3 px-4 font-semibold text-slate-800">{auth.telegram_username ? <a href={`https://t.me/${auth.telegram_username.replace(/^@+/, '')}`} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">@{auth.telegram_username.replace(/^@+/, '')}</a> : <span className="text-slate-400 font-light">未命名 / 群组</span>}</td>
                                  <td className="py-3 px-4 font-mono text-slate-500">{auth.telegram_chat_id}</td>
                                  <td className="py-3 px-4"><span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${auth.role === 'admin' ? 'bg-purple-50 text-purple-700 border border-purple-100' : auth.role === 'employee' ? 'bg-blue-50 text-blue-700 border border-blue-100' : 'bg-slate-100 text-slate-600'}`}>{auth.role === 'admin' ? '👑 管理员' : auth.role === 'employee' ? '🔑 员工' : '🟢 托管关联'}</span></td>
                                  <td className="py-3 px-4 text-slate-600">{auth.owner_username ? <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-100 font-medium">{auth.owner_username}</span> : <span className="text-slate-300 font-light">—</span>}</td>
                                  {!isTranslateBotType(editingBotNode.bot_type) && (
                                    <td className="py-3 px-4 text-right"><button type="button" onClick={() => openEditBotAuthModal(auth)} className="text-slate-400 hover:text-blue-600 font-bold mr-3">编辑</button><button type="button" onClick={() => deleteBotAuthorization(auth)} className="text-slate-400 hover:text-rose-600 font-bold">解除</button></td>
                                  )}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {botManageTab === 'reply' && !isTranslateBotType(editingBotNode.bot_type) && (
                      <div className="flex flex-col gap-4 animate-fade-in">
                        <div className="flex justify-between items-center bg-blue-500/5 p-3 rounded-2xl border border-blue-500/10 text-[11px] text-blue-700 font-medium">
                          <span>💡 <b>多话术随机防封机制已激活</b>：当客户首次私聊您绑定的电报账号时，系统会从以下启用的文本模板中<b>随机抽取一条</b>自动回复。</span>
                          <button type="button" onClick={openCreateBotReplyModal} className="px-3 py-1.5 bg-slate-900 text-white hover:bg-slate-800 rounded-lg text-[10px] font-black shrink-0 transition-all active:scale-[0.97]">➕ 新增自动回复文本</button>
                        </div>
                        {botAutoReplies.length === 0 ? (
                          <div className="py-8 text-center text-xs text-slate-400 bg-white border border-dashed border-slate-200 rounded-2xl">📭 暂无设置自动回复模板，系统将使用反诈声明作为默认兜底欢迎语。</div>
                        ) : (
                          <div className="flex flex-col gap-3">
                            {botAutoReplies.map((reply, idx) => (
                              <div key={reply.id || idx} className="bg-white border border-slate-100 p-4 rounded-2xl shadow-xs flex flex-col justify-between gap-3 hover:shadow-sm transition-shadow">
                                <div className="flex justify-between items-start">
                                  <div className="flex items-center gap-2"><span className="text-[10px] text-slate-400 font-mono"># {idx + 1}</span><span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${reply.is_enabled ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' : 'bg-slate-100 text-slate-400'}`}>{reply.is_enabled ? '🟢 激活中' : '⚪ 已停用'}</span></div>
                                  <div className="flex gap-2.5 text-[11px] font-bold"><button type="button" onClick={() => openEditBotReplyModal(reply)} className="text-slate-400 hover:text-blue-600 transition-colors">编辑</button><button type="button" onClick={() => deleteBotAutoReply(reply)} className="text-slate-400 hover:text-rose-600 transition-colors">删除</button></div>
                                </div>
                                <div className="text-xs text-slate-700 bg-slate-50/50 p-3 rounded-xl border border-slate-50 font-sans whitespace-pre-wrap leading-relaxed" dangerouslySetInnerHTML={{ __html: reply.reply_text }} />
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {showBotAuthModal && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col overflow-hidden">
              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <div>
                  <h3 className="font-bold text-slate-900 text-base">{editingBotAuthChatId ? '编辑 Bot 账号授权' : '手动新增 Bot 账号授权'}</h3>
                  <p className="text-xs text-slate-400 mt-0.5">为特定 Telegram 用户启用当前 Bot 的访问权限</p>
                </div>
                <button onClick={() => setShowBotAuthModal(false)} className="text-slate-400 hover:text-slate-600"><X className="w-5 h-5" /></button>
              </div>
              <div className="p-6 flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-600">授权 Bot 类型</label>
                  <select
                    value={selectedBotType}
                    onChange={(e) => setSelectedBotType(e.target.value)}
                    disabled={!!editingBotAuthChatId}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-xs font-medium bg-white disabled:bg-slate-50 disabled:text-slate-400"
                  >
                    <option value="ai_bot">AI 助手 (AI Bot)</option>
                    <option value="translate_bot">翻译助手 (Translate Bot)</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-600">电报 Chat ID</label>
                  <input value={botAuthChatId} onChange={(e) => setBotAuthChatId(e.target.value)} placeholder="例如: 8302461675" className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-xs font-medium" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-600">电报用户名 Username</label>
                  <input value={botAuthUsername} onChange={(e) => setBotAuthUsername(e.target.value)} placeholder="例如: RosePay_official" className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-xs font-medium" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-bold text-slate-600">角色权限</label>
                    <select value={botAuthRole} onChange={(e) => setBotAuthRole(e.target.value)} className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-xs font-medium bg-white">
                      <option value="employee">普通员工</option>
                      <option value="admin">超级管理员</option>
                      <option value="external">托管电报号</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-bold text-slate-600">状态</label>
                    <select value={botAuthActive} onChange={(e) => setBotAuthActive(Number(e.target.value))} className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-xs font-medium bg-white">
                      <option value={1}>启用</option>
                      <option value={0}>停用</option>
                    </select>
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-600">指派归属系统管理员 (可空)</label>
                  <select value={botAuthOwner} onChange={(e) => setBotAuthOwner(e.target.value)} className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-xs font-medium bg-white">
                    <option value="">未指派 (独立账号)</option>
                    {usersList.map((u) => (
                      <option key={u.id} value={u.username}>{u.username}</option>
                    ))}
                  </select>
                  <p className="text-[10px] text-slate-400">账号或者员工在后台名下所属的管理负责人账号。</p>
                </div>
              </div>
              <div className="p-5 border-t border-slate-100 flex justify-end gap-2 bg-slate-50/35">
                <button onClick={() => setShowBotAuthModal(false)} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg">取消</button>
                <button onClick={saveBotAuthorization} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg">保存授权</button>
              </div>
            </div>
          </div>
        )}

        {showBotReplyModal && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-lg flex flex-col overflow-hidden">
              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <div>
                  <h3 className="font-bold text-slate-900 text-base">{editingBotReplyId ? '编辑自动回复模板' : '新增自动回复模板'}</h3>
                  <p className="text-xs text-slate-400 mt-0.5">用于当前 Bot 类型的首问欢迎语或兜底回复</p>
                </div>
                <button onClick={() => setShowBotReplyModal(false)} className="text-slate-400 hover:text-slate-600"><X className="w-5 h-5" /></button>
              </div>
              <div className="p-6 flex flex-col gap-4">
                <textarea value={botReplyText} onChange={(e) => setBotReplyText(e.target.value)} rows={8} placeholder="请输入自动回复内容，支持 Telegram HTML 简单排版" className="w-full px-3.5 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-xs leading-relaxed" />
                <label className="flex items-center gap-2 text-xs font-bold text-slate-700">
                  <input type="checkbox" checked={botReplyEnabled === 1} onChange={(e) => setBotReplyEnabled(e.target.checked ? 1 : 0)} className="w-3.5 h-3.5 text-blue-600 rounded-sm border-slate-300" />
                  启用此模板
                </label>
              </div>
              <div className="p-5 border-t border-slate-100 flex justify-end gap-2 bg-slate-50/35">
                <button onClick={() => setShowBotReplyModal(false)} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg">取消</button>
                <button onClick={saveBotAutoReply} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg">保存模板</button>
              </div>
            </div>
          </div>
        )}

        {showGeminiConfigModal && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
              
              {/* Header */}
              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <div>
                  <h3 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                    <Key className="w-4 h-4 text-blue-500" />
                    配置 Gemini API 密钥
                  </h3>
                  <p className="text-[10px] text-slate-400 mt-0.5">配置您的 Google AI Studio API Key，用于智能搜群时的消息分析。</p>
                </div>
                <button
                  onClick={() => setShowGeminiConfigModal(false)}
                  className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Body */}
              <div className="p-5 flex flex-col gap-4 text-xs">
                <div className="flex flex-col gap-1.5">
                  <label className="font-semibold text-slate-500">API 密钥 (API Key)</label>
                  <input
                    type="password"
                    value={newGeminiKey}
                    onChange={(e) => setNewGeminiKey(e.target.value)}
                    placeholder="输入 AI Studio API Key..."
                    className="w-full text-xs bg-slate-50 border border-slate-100 rounded-xl px-3 py-2.5 focus:outline-none focus:border-blue-500 focus:bg-white transition-all font-mono"
                  />
                  <span className="text-[10px] text-slate-400 mt-1 leading-normal">
                    如果您没有密钥，可前往 <a href="https://aistudio.google.com/" target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">Google AI Studio</a> 免费获取。
                  </span>
                </div>
              </div>

              {/* Footer */}
              <div className="p-5 border-t border-slate-100 flex justify-end gap-3 bg-slate-50/50">
                <button
                  onClick={() => setShowGeminiConfigModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-all"
                >
                  取消
                </button>
                <button
                  onClick={saveGeminiKey}
                  disabled={savingGeminiKey || !newGeminiKey.trim()}
                  className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 rounded-lg transition-all shadow-sm flex items-center gap-1"
                >
                  {savingGeminiKey ? '正在保存...' : '💾 保存配置'}
                </button>
              </div>

            </div>
          </div>
        )}


        {/* I. LOGIN HISTORY LOGS MODAL */}

        {showLoginLogsModal && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-4xl flex flex-col max-h-[85vh] overflow-hidden">

              

              {/* Modal Header */}

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">

                    <span>📝 登录与导入历史记录</span>

                  </h3>

                  <p className="text-xs text-slate-400 mt-0.5 font-light">

                    记录每一次批量导入与手动登录尝试的详细凭证及状态信息

                  </p>

                </div>

                <div className="flex items-center gap-2">

                  <button

                    onClick={fetchLoginLogs}

                    className="p-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5"

                    title="刷新日志"

                  >

                    <RefreshCw className="w-3.5 h-3.5" />

                  </button>

                  <button

                    onClick={() => {

                      if (confirm("确定要清空全部登录历史记录吗？（此操作不可恢复）")) {

                        handleClearLoginLogs();

                      }

                    }}

                    className="px-3 py-2 bg-rose-50 border border-rose-100 hover:bg-rose-100 text-rose-600 rounded-lg text-xs font-semibold shadow-xs transition-colors"

                  >

                    清空历史记录

                  </button>

                  <button 

                    onClick={() => {

                      setShowLoginLogsModal(false);

                      setLoginLogs([]);

                    }}

                    className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                  >

                    <X className="w-5 h-5" />

                  </button>

                </div>

              </div>



              {/* Modal Body */}

              <div className="p-6 overflow-y-auto flex-grow bg-slate-50/20">

                {loginLogs.length === 0 ? (

                  <div className="flex flex-col items-center justify-center py-20 text-slate-400 gap-3">

                    <FileText className="w-12 h-12 opacity-20" />

                    <span className="text-xs font-light">暂无登录历史记录</span>

                  </div>

                ) : (

                  <div className="border border-slate-150 rounded-xl overflow-hidden bg-white shadow-sm">

                    <table className="w-full text-left border-collapse table-fixed">

                      <thead>

                        <tr className="border-b border-slate-100 bg-slate-50/50 text-[10px] font-bold uppercase text-slate-500 tracking-wider">

                          <th className="py-3 px-4 w-[16%]">时间戳</th>

                          <th className="py-3 px-4 w-[16%]">手机号</th>

                          <th className="py-3 px-4 w-[12%]">登录方式</th>

                          <th className="py-3 px-4 w-[24%]">API 接码链接</th>

                          <th className="py-3 px-4 w-[11%]">原始 2FA</th>

                          <th className="py-3 px-4 w-[11%]">当前 2FA</th>

                          <th className="py-3 px-4 w-[10%] text-center">状态</th>

                        </tr>

                      </thead>

                      <tbody className="divide-y divide-slate-100 text-xs">

                        {loginLogs.map((log) => {

                          // Clean / parse API link for displaying page_id

                          let pageId = '';

                          if (log.api_link) {

                            const match = log.api_link.match(/(?:https?:\/\/[^\/]+\/)?([a-zA-Z0-9\-]+)(?:\/GetHTML)?/);

                            pageId = match ? match[1] : log.api_link;

                          }

                          

                          return (

                            <tr key={log.id} className="hover:bg-slate-50/50 transition-colors">

                              <td className="py-3 px-4 text-slate-500 font-mono text-[11px] truncate" title={log.timestamp}>

                                {log.timestamp}

                              </td>

                              <td className="py-3 px-4 text-slate-800 font-semibold truncate" title={log.phone}>

                                {log.phone}

                              </td>

                              <td className="py-3 px-4">

                                <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${

                                  log.login_type === 'import' 

                                    ? 'bg-purple-50 text-purple-600 border-purple-100' 

                                    : 'bg-blue-50 text-blue-600 border-blue-100'

                                }`}>

                                  {log.login_type === 'import' ? '批量导入' : '手动登录'}

                                </span>

                              </td>

                              <td className="py-3 px-4">

                                {log.api_link ? (

                                  <div className="flex items-center gap-1.5 justify-between max-w-full">

                                    <span 

                                      className="font-mono text-slate-500 select-all truncate text-[10px]"

                                      title={log.api_link}

                                    >

                                      {pageId.length > 15 ? `${pageId.substring(0, 15)}...` : pageId}

                                    </span>

                                    <button

                                      onClick={() => {

                                        navigator.clipboard.writeText(log.api_link);

                                        setToastText("API链接已复制");

                                        setTimeout(() => setToastText(''), 1500);

                                      }}

                                      className="p-1 hover:bg-slate-100 rounded text-slate-400 hover:text-blue-500 shrink-0 transition-colors"

                                      title="复制完整API链接"

                                    >

                                      <Copy className="w-3 h-3" />

                                    </button>

                                  </div>

                                ) : (

                                  <span className="text-slate-300 italic font-light">---</span>

                                )}

                              </td>

                              <td className="py-3 px-4 font-mono text-slate-600 truncate" title={log.original_password || ''}>

                                {log.original_password || <span className="text-slate-300 italic font-light">---</span>}

                              </td>

                              <td className="py-3 px-4 font-mono text-slate-600 truncate" title={log.current_password || ''}>

                                {log.current_password || <span className="text-slate-300 italic font-light">---</span>}

                              </td>

                              <td className="py-3 px-4 text-center">

                                {log.status === 'success' ? (

                                  <span className="px-2 py-0.5 bg-emerald-50 text-emerald-600 border border-emerald-100 rounded text-[10px] font-bold">

                                    成功

                                  </span>

                                ) : (

                                  <span 

                                    className="px-2 py-0.5 bg-rose-50 text-rose-600 border border-rose-100 rounded text-[10px] font-bold cursor-help"

                                    title={log.error_detail || '未知原因失败'}

                                  >

                                    失败

                                  </span>

                                )}

                              </td>

                            </tr>

                          );

                        })}

                      </tbody>

                    </table>

                  </div>

                )}

              </div>



              {/* Modal Footer */}

              <div className="p-5 border-t border-slate-100 flex justify-end bg-slate-50/35">

                <button 

                  onClick={() => {

                    setShowLoginLogsModal(false);

                    setLoginLogs([]);

                  }}

                  className="px-6 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-lg transition-all"

                >

                  关闭

                </button>

              </div>



            </div>

          </div>

        )}



        {groupJoinTarget && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-[60] flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md overflow-hidden">

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">打开群组链接</h3>

                  <p className="text-xs text-slate-400 mt-0.5">确认后会在新窗口打开 Telegram 群组页面</p>

                </div>

                <button

                  onClick={() => setGroupJoinTarget(null)}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>

              <div className="p-5 space-y-4">

                <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 space-y-2">

                  <div className="text-sm font-bold text-slate-900 truncate" title={groupJoinTarget.title}>

                    {groupJoinTarget.title || '未命名群组'}

                  </div>

                  <div className="text-xs font-mono text-blue-600 truncate">

                    @{groupJoinTarget.username.replace(/^@+/, '')}

                  </div>

                  <div className="text-[11px] font-mono text-slate-400 break-all">

                    {getGroupTelegramLink(groupJoinTarget)}

                  </div>

                </div>

                <p className="text-[11px] leading-relaxed text-slate-400">

                  这个操作只是打开 Telegram 链接，是否加入由 Telegram 页面或客户端确认。

                </p>

              </div>

              <div className="p-5 border-t border-slate-100 flex justify-end gap-2 bg-slate-50/35">

                <button

                  onClick={() => setGroupJoinTarget(null)}

                  className="px-5 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-lg transition-all"

                >

                  取消

                </button>

                <button

                  onClick={() => {

                    const link = getGroupTelegramLink(groupJoinTarget);

                    if (link) {

                      window.open(link, '_blank', 'noopener,noreferrer');

                    }

                    setGroupJoinTarget(null);

                  }}

                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-all shadow-sm inline-flex items-center gap-1.5"

                >

                  <ExternalLink className="w-4 h-4" />

                  <span>打开 Telegram 加入</span>

                </button>

              </div>

            </div>

          </div>

        )}

        {/* showAddGroupModal */}

        {showAddGroupModal && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col overflow-hidden">

              

              {/* Modal Header */}

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">添加 Telegram 群组</h3>

                  <p className="text-xs text-slate-400 mt-0.5">支持群组链接、邀请链接、用户名或 ID (每行一个)</p>

                </div>

                <button 

                  onClick={() => {

                    setShowAddGroupModal(false);

                    setNewGroupLinks('');

                    setNewGroupCategory('中文广告');

                  }}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              {/* Modal Body */}

              <div className="p-6 flex flex-col gap-4">

                <div className="flex flex-col gap-1.5">

                  <label className="text-xs font-semibold text-slate-700">群组/频道链接或标识符列表 (每行一个)</label>

                  <textarea 

                    value={newGroupLinks}

                    onChange={(e) => setNewGroupLinks(e.target.value)}

                    placeholder="请输入链接，每行一个。例如:&#10;https://t.me/RosePayChannel&#10;@RosePayChannel&#10;RosePayChannel"

                    className="w-full h-36 bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-blue-500 font-mono resize-none transition-all"

                    disabled={resolvingGroup}

                  />

                  <p className="text-[10px] text-slate-400 leading-normal mt-1">

                    系统将通过您已登录的 Telegram 账号向 Telegram 官方 API 请求校验这批群组或频道的真实性，校验成功后将自动拉取标题、人数等信息并保存。

                  </p>

                </div>



                {/* Category Selection */}

                <div className="flex flex-col gap-2">

                  <label className="text-xs font-semibold text-slate-700">广告类型 (单选)</label>

                  <div className="flex gap-4">

                    <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none font-medium">

                      <input 

                        type="radio" 

                        name="newGroupCategory" 

                        value="中文广告"

                        checked={newGroupCategory === '中文广告'}

                        onChange={() => setNewGroupCategory('中文广告')}

                        className="text-blue-600 focus:ring-blue-500/20 border-slate-300"

                        disabled={resolvingGroup}

                      />

                      <span>中文广告</span>

                    </label>

                    <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none font-medium">

                      <input 

                        type="radio" 

                        name="newGroupCategory" 

                        value="英文广告"

                        checked={newGroupCategory === '英文广告'}

                        onChange={() => setNewGroupCategory('英文广告')}

                        className="text-blue-600 focus:ring-blue-500/20 border-slate-300"

                        disabled={resolvingGroup}

                      />

                      <span>英文广告</span>

                    </label>

                  </div>

                </div>



                {resolvingGroup && (

                  <div className="bg-blue-50 border border-blue-100 rounded-lg p-3.5 flex items-center gap-2.5 text-xs text-blue-700">

                    <RefreshCw className="w-4 h-4 animate-spin text-blue-500 shrink-0" />

                    <span>正在通过电报 API 校验该链接，这可能需要几秒钟...</span>

                  </div>

                )}

              </div>



              {/* Modal Footer */}

              <div className="p-5 border-t border-slate-100 flex justify-end gap-2.5 bg-slate-50/35">

                <button 

                  onClick={() => {

                    setShowAddGroupModal(false);

                    setNewGroupLinks('');

                    setNewGroupCategory('中文广告');

                  }}

                  disabled={resolvingGroup}

                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 disabled:opacity-50 text-slate-700 text-xs font-bold rounded-lg transition-all"

                >

                  取消

                </button>

                <button 

                  onClick={handleResolveGroup}

                  disabled={resolvingGroup}

                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-xs font-bold rounded-lg transition-all shadow-sm"

                >

                  {resolvingGroup ? '正在校验...' : '保存'}

                </button>

              </div>



            </div>

          </div>

        )}

        {/* showGroupSyncExecutionModal */}

        {showGroupSyncExecutionModal && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-[60] flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-4xl flex flex-col max-h-[88vh] overflow-hidden">

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">群组同步执行日志</h3>

                  <p className="text-xs text-slate-400 mt-0.5">同步过程会显示执行账号、目标群组、返回结果、等待与最终汇总</p>

                </div>

                <button

                  onClick={() => setShowGroupSyncExecutionModal(false)}

                  disabled={groupSyncRunning}

                  className="w-8 h-8 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>

              <div className="p-5 overflow-y-auto flex flex-col gap-4">

                <div className="rounded-2xl bg-slate-950 border border-slate-800 shadow-inner overflow-hidden">

                  <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">

                    <span className="text-xs font-bold text-slate-200">执行流水</span>

                    <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${groupSyncRunning ? 'bg-blue-500/15 text-blue-300' : 'bg-emerald-500/15 text-emerald-300'}`}>

                      {groupSyncRunning ? '执行中' : '已结束'}

                    </span>

                  </div>

                  <div className="h-80 overflow-y-auto p-4 font-mono text-[11px] leading-relaxed text-slate-200">

                    {groupSyncExecutionLogs.length === 0 ? (

                      <div className="text-slate-500">等待开始执行...</div>

                    ) : (

                      groupSyncExecutionLogs.map((line, index) => (

                        <div key={`${index}-${line}`} className="whitespace-pre-wrap break-words">

                          {line}

                        </div>

                      ))

                    )}

                  </div>

                </div>

                {groupSyncSummary && (

                  <div className="rounded-2xl border border-slate-100 overflow-hidden">

                    <div className="px-4 py-3 bg-slate-50 border-b border-slate-100 flex items-center justify-between">

                      <span className="text-xs font-bold text-slate-700">最终汇总</span>

                      <span className="text-[10px] text-slate-400">质量评分会在质量检测功能接入后显示</span>

                    </div>

                    <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-3">

                      {[
                        ['新增', groupSyncSummary.addedCount],
                        ['状态更新', groupSyncSummary.updatedCount],
                        ['本次禁用', groupSyncSummary.disabledCount],
                        ['失效', groupSyncSummary.invalidCount],
                      ].map(([label, value]) => (

                        <div key={String(label)} className="rounded-xl bg-slate-50/60 border border-slate-100 p-3">

                          <div className="text-[10px] text-slate-400 font-bold">{label}</div>

                          <div className="text-xl font-black text-slate-900 mt-1 font-mono">{value}</div>

                        </div>

                      ))}

                    </div>

                    <div className="px-4 pb-4 grid grid-cols-1 md:grid-cols-2 gap-3">

                      <div className="rounded-xl border border-slate-100 overflow-hidden">

                        <div className="px-3 py-2 bg-slate-50 text-[11px] font-bold text-slate-600">成员数区间</div>

                        {Object.entries(groupSyncSummary.memberRanges).map(([label, count]) => (

                          <div key={label} className="px-3 py-2 flex justify-between text-xs border-t border-slate-100">

                            <span className="text-slate-500">{label}</span>

                            <span className="font-black font-mono text-slate-900">{count}</span>

                          </div>

                        ))}

                      </div>

                      <div className="rounded-xl border border-slate-100 overflow-hidden">

                        <div className="px-3 py-2 bg-slate-50 text-[11px] font-bold text-slate-600">质量评分区间</div>

                        {Object.entries(groupSyncSummary.scoreRanges).map(([label, count]) => (

                          <div key={label} className="px-3 py-2 flex justify-between text-xs border-t border-slate-100">

                            <span className="text-slate-500">{label}</span>

                            <span className="font-black font-mono text-slate-900">{count}</span>

                          </div>

                        ))}

                      </div>

                    </div>

                  </div>

                )}

              </div>

              <div className="p-5 border-t border-slate-100 flex justify-end bg-slate-50/35">

                <button

                  onClick={() => setShowGroupSyncExecutionModal(false)}

                  disabled={groupSyncRunning}

                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed text-white text-xs font-bold rounded-lg transition-all shadow-sm"

                >

                  {groupSyncRunning ? '执行中...' : '关闭'}

                </button>

              </div>

            </div>

          </div>

        )}

        {/* showGroupSyncSummaryModal */}

        {showGroupSyncSummaryModal && groupSyncSummary && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-[60] flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-2xl flex flex-col max-h-[85vh] overflow-hidden">

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">群组同步结果</h3>

                  <p className="text-xs text-slate-400 mt-0.5">本次同步后的群组状态与分布统计</p>

                </div>

                <button

                  onClick={() => setShowGroupSyncSummaryModal(false)}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>

              <div className="p-5 overflow-y-auto flex flex-col gap-4">

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">

                  {[
                    ['同步读取', groupSyncSummary.syncedCount],
                    ['新增群组', groupSyncSummary.addedCount],
                    ['状态更新', groupSyncSummary.updatedCount],
                    ['本次禁用', groupSyncSummary.disabledCount],
                  ].map(([label, value]) => (

                    <div key={String(label)} className="rounded-xl border border-slate-100 bg-slate-50/50 p-3">

                      <div className="text-[10px] text-slate-400 font-bold">{label}</div>

                      <div className="text-2xl font-black text-slate-900 mt-1 font-mono">{value}</div>

                    </div>

                  ))}

                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                  <div className="rounded-xl border border-slate-100 overflow-hidden">

                    <div className="px-4 py-3 bg-slate-50 text-xs font-bold text-slate-700 border-b border-slate-100">当前群组状态</div>

                    <div className="p-4 grid grid-cols-3 gap-3 text-center">

                      <div>

                        <div className="text-[10px] text-slate-400">总数</div>

                        <div className="text-lg font-black text-slate-900 font-mono">{groupSyncSummary.totalGroups}</div>

                      </div>

                      <div>

                        <div className="text-[10px] text-slate-400">启用</div>

                        <div className="text-lg font-black text-emerald-600 font-mono">{groupSyncSummary.enabledCount}</div>

                      </div>

                      <div>

                        <div className="text-[10px] text-slate-400">禁用</div>

                        <div className="text-lg font-black text-rose-600 font-mono">{groupSyncSummary.disabledTotalCount}</div>

                      </div>

                    </div>

                  </div>

                  <div className="rounded-xl border border-slate-100 overflow-hidden">

                    <div className="px-4 py-3 bg-slate-50 text-xs font-bold text-slate-700 border-b border-slate-100">异常结果</div>

                    <div className="p-4 grid grid-cols-3 gap-3 text-center">

                      <div>

                        <div className="text-[10px] text-slate-400">失效群</div>

                        <div className="text-lg font-black text-rose-600 font-mono">{groupSyncSummary.invalidCount}</div>

                      </div>

                      <div>

                        <div className="text-[10px] text-slate-400">已存在</div>

                        <div className="text-lg font-black text-slate-700 font-mono">{groupSyncSummary.skippedCount}</div>

                      </div>

                      <div>

                        <div className="text-[10px] text-slate-400">错误</div>

                        <div className="text-lg font-black text-amber-600 font-mono">{groupSyncSummary.errors.length}</div>

                      </div>

                    </div>

                  </div>

                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                  <div className="rounded-xl border border-slate-100 overflow-hidden">

                    <div className="px-4 py-3 bg-slate-50 text-xs font-bold text-slate-700 border-b border-slate-100">成员数区间</div>

                    <div className="divide-y divide-slate-100">

                      {Object.entries(groupSyncSummary.memberRanges).map(([label, count]) => (

                        <div key={label} className="px-4 py-2.5 flex items-center justify-between text-xs">

                          <span className="text-slate-500">{label}</span>

                          <span className="font-black text-slate-900 font-mono">{count}</span>

                        </div>

                      ))}

                    </div>

                  </div>

                  <div className="rounded-xl border border-slate-100 overflow-hidden">

                    <div className="px-4 py-3 bg-slate-50 text-xs font-bold text-slate-700 border-b border-slate-100">质量评分区间</div>

                    <div className="divide-y divide-slate-100">

                      {Object.entries(groupSyncSummary.scoreRanges).map(([label, count]) => (

                        <div key={label} className="px-4 py-2.5 flex items-center justify-between text-xs">

                          <span className="text-slate-500">{label}</span>

                          <span className="font-black text-slate-900 font-mono">{count}</span>

                        </div>

                      ))}

                    </div>

                    {!groupSyncSummary.hasScore && (

                      <div className="px-4 py-3 text-[10px] text-slate-400 bg-slate-50 border-t border-slate-100">

                        当前版本还未执行群组质量检测，评分区间会在质量检测功能接入后自动显示。

                      </div>

                    )}

                  </div>

                </div>

                {(groupSyncSummary.invalidGroups.length > 0 || groupSyncSummary.errors.length > 0) && (

                  <div className="rounded-xl border border-amber-100 bg-amber-50/40 overflow-hidden">

                    <div className="px-4 py-3 text-xs font-bold text-amber-700 border-b border-amber-100">需要关注</div>

                    <div className="p-4 max-h-40 overflow-y-auto text-[11px] text-amber-800 leading-relaxed space-y-1">

                      {groupSyncSummary.invalidGroups.slice(0, 12).map((group) => (

                        <div key={group.id}>失效群：{group.title || group.id} {group.username ? `(@${group.username})` : ''}</div>

                      ))}

                      {groupSyncSummary.errors.slice(0, 8).map((err, index) => (

                        <div key={`err-${index}`}>错误：{err}</div>

                      ))}

                    </div>

                  </div>

                )}

              </div>

              <div className="p-5 border-t border-slate-100 flex justify-end bg-slate-50/35">

                <button

                  onClick={() => setShowGroupSyncSummaryModal(false)}

                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-all shadow-sm"

                >

                  知道了

                </button>

              </div>

            </div>

          </div>

        )}

        {/* showManageCategoriesModal */}

        {showManageCategoriesModal && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-md flex flex-col overflow-hidden">

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">管理群组类型</h3>

                  <p className="text-xs text-slate-400 mt-0.5">维护群组库里可选的分类标签</p>

                </div>

                <button

                  onClick={() => {

                    setShowManageCategoriesModal(false);

                    setNewCategoryName('');

                  }}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>

              <div className="p-5 flex flex-col gap-4">

                <div className="flex gap-2">

                  <input

                    value={newCategoryName}

                    onChange={(e) => setNewCategoryName(e.target.value)}

                    onKeyDown={(e) => {

                      if (e.key === 'Enter') {

                        handleAddGroupCategory();

                      }

                    }}

                    placeholder="输入新的群组类型名称"

                    className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-blue-500 transition-all"

                  />

                  <button

                    onClick={handleAddGroupCategory}

                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-all shadow-sm"

                  >

                    添加

                  </button>

                </div>

                <div className="border border-slate-100 rounded-xl overflow-hidden bg-slate-50/30 max-h-80 overflow-y-auto">

                  {groupCategories.length === 0 ? (

                    <div className="py-10 text-center text-xs text-slate-400">暂无群组类型</div>

                  ) : (

                    <div className="divide-y divide-slate-100">

                      {groupCategories.map((category) => (

                        <div key={`${category.company}-${category.name}`} className="flex items-center justify-between gap-3 px-4 py-3 bg-white">

                          <div className="min-w-0">

                            <div className="text-sm font-bold text-slate-800 truncate">{category.name}</div>

                            <div className="text-[10px] text-slate-400 font-mono">{category.company}</div>

                          </div>

                          <div className="flex items-center gap-2 shrink-0">

                            <button

                              onClick={() => handleRenameGroupCategory(category.name)}

                              className="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 text-[10px] font-bold rounded-lg transition-all"

                            >

                              重命名

                            </button>

                            <button

                              onClick={() => handleDeleteGroupCategory(category.name)}

                              className="px-2.5 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-600 text-[10px] font-bold rounded-lg transition-all"

                            >

                              删除

                            </button>

                          </div>

                        </div>

                      ))}

                    </div>

                  )}

                </div>

              </div>

              <div className="p-5 border-t border-slate-100 flex justify-end bg-slate-50/35">

                <button

                  onClick={() => {

                    setShowManageCategoriesModal(false);

                    setNewCategoryName('');

                  }}

                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-lg transition-all"

                >

                  关闭

                </button>

              </div>

            </div>

          </div>

        )}

        {/* showBatchResultModal */}

        {showBatchResultModal && batchResult && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-[60] flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-lg flex flex-col max-h-[80vh] overflow-hidden">

              

              {/* Modal Header */}

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">批量导入群组结果</h3>

                  <p className="text-xs text-slate-400 mt-0.5">导入流程已完成，详细报告如下</p>

                </div>

                <button 

                  onClick={() => {

                    setShowBatchResultModal(false);

                    setBatchResult(null);

                  }}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              {/* Modal Body */}

              <div className="p-6 overflow-y-auto flex flex-col gap-5">

                {/* Stats Summary */}

                <div className="grid grid-cols-2 gap-4">

                  <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4 text-center">

                    <div className="text-xs text-emerald-600 font-semibold uppercase tracking-wider">成功导入</div>

                    <div className="text-3xl font-extrabold text-emerald-700 mt-1">{batchResult.successCount} <span className="text-sm font-normal text-emerald-500">个</span></div>

                  </div>

                  <div className="bg-rose-50 border border-rose-100 rounded-xl p-4 text-center">

                    <div className="text-xs text-rose-600 font-semibold uppercase tracking-wider">失败数量</div>

                    <div className="text-3xl font-extrabold text-rose-700 mt-1">{batchResult.failedCount} <span className="text-sm font-normal text-rose-500">个</span></div>

                  </div>

                </div>



                {/* Error Details */}

                {batchResult.errorDetails.length > 0 && (

                  <div className="flex flex-col gap-2">

                    <label className="text-xs font-semibold text-slate-600">失败详情及原因</label>

                    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 font-mono text-xs text-slate-700 flex flex-col gap-2.5 max-h-[40vh] overflow-y-auto">

                      {batchResult.errorDetails.map((detail, idx) => (

                        <div key={idx} className="border-b border-slate-200/50 last:border-0 pb-2 last:pb-0 leading-relaxed">

                          <span className="text-rose-600 font-semibold mr-1">●</span> {detail}

                        </div>

                      ))}

                    </div>

                  </div>

                )}

              </div>



              {/* Modal Footer */}

              <div className="p-5 border-t border-slate-100 flex justify-end bg-slate-50/35">

                <button 

                  onClick={() => {

                    setShowBatchResultModal(false);

                    setBatchResult(null);

                  }}

                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-all shadow-md shadow-blue-600/10 active:scale-[0.98]"

                >

                  确定

                </button>

              </div>



            </div>

          </div>

        )}



        {/* F_AVATAR. BATCH MODIFY ACCOUNTS AVATAR MODAL */}

        {showBatchAvatarModal && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-lg flex flex-col max-h-[85vh] overflow-hidden">

              

              {/* Modal Header */}

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">批量修改头像</h3>

                  <p className="text-xs text-slate-400 mt-0.5 font-light">已选择 {batchEditTargetIds.length} 个账号</p>

                </div>

                <button 

                  onClick={() => {

                    setShowBatchAvatarModal(false);

                    setBatchAvatarFiles(null);

                    setSelectedBatchLibraryAvatarNames([]);

                  }}

                  disabled={updatingAvatar}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              {/* Modal Body */}

              <div className="p-6 overflow-y-auto flex flex-col gap-5">

                

                {/* Source Toggle */}

                <div className="flex bg-slate-100 p-0.5 rounded-lg shrink-0">

                  <button

                    type="button"

                    onClick={() => setBatchAvatarSource('local')}

                    className={`flex-1 py-1.5 text-center text-xs font-semibold rounded-md transition-all ${

                      batchAvatarSource === 'local' 

                        ? 'bg-white text-slate-800 shadow-xs' 

                        : 'text-slate-500 hover:text-slate-800'

                    }`}

                  >

                    选择本地文件自己上传

                  </button>

                  <button

                    type="button"

                    onClick={() => {

                      setBatchAvatarSource('library');

                      fetchAvatarLibrary();

                    }}

                    className={`flex-1 py-1.5 text-center text-xs font-semibold rounded-md transition-all ${

                      batchAvatarSource === 'library' 

                        ? 'bg-white text-slate-800 shadow-xs' 

                        : 'text-slate-500 hover:text-slate-800'

                    }`}

                  >

                    从头像库中选择

                  </button>

                </div>



                {/* Local Upload Form */}

                {batchAvatarSource === 'local' && (

                  <div className="flex flex-col gap-5">

                    <div className="flex flex-col gap-1.5">

                      <label className="text-xs text-slate-600 font-semibold">选择图片文件 (可多选，支持 JPG/PNG)</label>

                      <input 

                        type="file" 

                        accept="image/*"

                        multiple

                        onChange={(e) => setBatchAvatarFiles(e.target.files)}

                        className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 text-xs text-slate-800 focus:outline-none focus:bg-white focus:border-blue-500"

                        disabled={updatingAvatar}

                      />

                      <p className="text-[10px] text-slate-400 leading-normal">

                        支持单张图片或多张图片。若选择多张，系统将轮流（Round-Robin）为各账号分配不同的头像。

                      </p>

                    </div>



                    {batchAvatarFiles && batchAvatarFiles.length > 0 && (

                      <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 flex flex-col gap-1 text-xs">

                        <span className="font-bold text-slate-600 text-[10px] uppercase">已选择的文件 ({batchAvatarFiles.length})：</span>

                        <ul className="list-disc list-inside text-slate-500 font-mono text-[11px] truncate max-h-[100px] overflow-y-auto">

                          {Array.from(batchAvatarFiles).map((file, i) => (

                            <li key={i} className="truncate">{file.name} ({(file.size / 1024).toFixed(1)} KB)</li>

                          ))}

                        </ul>

                      </div>

                    )}

                  </div>

                )}



                {/* Library Selector Form */}

                {batchAvatarSource === 'library' && (

                  <div className="flex flex-col gap-3">

                    <div className="flex justify-between items-center text-xs text-slate-500">

                      <span>可多选头像进行轮流分配</span>

                      <span className="font-semibold text-blue-600">已选择 {selectedBatchLibraryAvatarNames.length} 个</span>

                    </div>



                    {avatarLibrary.length === 0 ? (

                      <div className="text-center py-8 text-slate-400 border border-dashed border-slate-200 rounded-xl bg-slate-50/20 text-xs">

                        头像库目前为空。请在主页面点击“头像库管理”按钮上传头像。

                      </div>

                    ) : (

                      <div className="grid grid-cols-4 gap-2.5 max-h-[300px] overflow-y-auto p-1">

                        {avatarLibrary.map((item) => {

                          const isSelected = selectedBatchLibraryAvatarNames.includes(item.name);

                          const backendUrl = BASE_URL;

                          const imgUrl = `${backendUrl}/api/avatar-library/file/${encodeURIComponent(item.name)}`;



                          return (

                            <div 

                              key={item.name}

                              onClick={() => {

                                if (isSelected) {

                                  setSelectedBatchLibraryAvatarNames(prev => prev.filter(n => n !== item.name));

                                } else {

                                  setSelectedBatchLibraryAvatarNames(prev => [...prev, item.name]);

                                }

                              }}

                              className={`relative aspect-square rounded-xl overflow-hidden border-2 cursor-pointer transition-all select-none hover:scale-[1.03] ${

                                isSelected ? 'border-blue-500 ring-2 ring-blue-500/25' : 'border-slate-100 hover:border-slate-300'

                              }`}

                              title={item.name}

                            >

                              <img src={imgUrl} alt={item.name} className="w-full h-full object-cover" />

                              {isSelected && (

                                <div className="absolute inset-0 bg-blue-500/20 flex items-center justify-center">

                                  <div className="bg-blue-600 text-white rounded-full p-0.5">

                                    <Check className="w-4 h-4" />

                                  </div>

                                </div>

                              )}

                            </div>

                          );

                        })}

                      </div>

                    )}

                  </div>

                )}



              </div>



              {/* Modal Footer */}

              <div className="p-5 border-t border-slate-100 flex justify-end bg-slate-50/35 gap-2">

                <button 

                  onClick={() => {

                    setShowBatchAvatarModal(false);

                    setBatchAvatarFiles(null);

                    setSelectedBatchLibraryAvatarNames([]);

                  }}

                  disabled={updatingAvatar}

                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 transition-colors"

                >

                  取消

                </button>

                <button

                  onClick={handleBatchUpdateAvatars}

                  disabled={updatingAvatar || (batchAvatarSource === 'local' ? (!batchAvatarFiles || batchAvatarFiles.length === 0) : (selectedBatchLibraryAvatarNames.length === 0))}

                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-xs font-bold rounded-lg shadow-sm transition-all flex items-center gap-1.5"

                >

                  {updatingAvatar ? (

                    <>

                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />

                      <span>正在修改...</span>

                    </>

                  ) : (

                    <span>保存并执行</span>

                  )}

                </button>

              </div>



            </div>

          </div>

        )}



        {/* G_AVATAR_LIBRARY. AVATAR LIBRARY MANAGER MODAL */}

        {showLibraryManager && (

          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">

            <div className="bg-white rounded-2xl border border-slate-100 shadow-xl w-full max-w-2xl flex flex-col max-h-[85vh] overflow-hidden">

              

              {/* Modal Header */}

              <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">

                <div>

                  <h3 className="font-bold text-slate-900 text-base">🖼️ 头像库管理</h3>

                  <p className="text-xs text-slate-400 mt-0.5 font-light">上传、修改或删除服务器上的共享头像，所有模块可实时同步选择</p>

                </div>

                <button 

                  onClick={() => {

                    setShowLibraryManager(false);

                    setRenamingAvatarName('');

                  }}

                  className="w-8 h-8 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"

                >

                  <X className="w-5 h-5" />

                </button>

              </div>



              {/* Modal Body */}

              <div className="p-6 overflow-y-auto flex flex-col gap-6">

                

                {/* Upload Section */}

                <div className="border border-dashed border-slate-200 hover:border-blue-400 rounded-xl p-6 bg-slate-50/50 transition-colors flex flex-col items-center justify-center gap-2 group relative">

                  <input 

                    type="file" 

                    accept="image/*"

                    multiple

                    onChange={(e) => {

                      if (e.target.files && e.target.files.length > 0) {

                        handleUploadToAvatarLibrary(e.target.files);

                      }

                    }}

                    className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"

                    disabled={uploadingToLibrary}

                  />

                  <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-600 group-hover:scale-110 transition-transform">

                    {uploadingToLibrary ? (

                      <RefreshCw className="w-5 h-5 animate-spin" />

                    ) : (

                      <Upload className="w-5 h-5" />

                    )}

                  </div>

                  <div className="text-center">

                    <p className="text-xs font-semibold text-slate-700">点击或将图片拖拽到此处上传</p>

                    <p className="text-[10px] text-slate-400 mt-0.5">支持多选，大小限制为 10MB 以内，格式支持 JPG/PNG/WEBP/GIF</p>

                  </div>

                </div>



                {/* Headshot Grid */}

                <div className="flex flex-col gap-2">

                  <div className="text-xs text-slate-500 font-semibold uppercase tracking-wider">

                    头像列表 ({avatarLibrary.length})

                  </div>



                  {avatarLibrary.length === 0 ? (

                    <div className="text-center py-12 text-slate-400 border border-slate-100 rounded-xl bg-slate-50/20 text-xs">

                      头像库目前没有任何图片，请在上方区域上传。

                    </div>

                  ) : (

                    <div className="grid grid-cols-3 sm:grid-cols-4 gap-4 max-h-[350px] overflow-y-auto p-1">

                      {avatarLibrary.map((item) => {

                        const isRenaming = renamingAvatarName === item.name;

                        const backendUrl = BASE_URL;

                        const imgUrl = `${backendUrl}/api/avatar-library/file/${encodeURIComponent(item.name)}`;



                        return (

                          <div 

                            key={item.name} 

                            className="bg-white border border-slate-100 rounded-xl overflow-hidden shadow-sm flex flex-col group/card hover:shadow-md transition-shadow"

                          >

                            {/* Image Container */}

                            <div className="relative aspect-square bg-slate-50 overflow-hidden">

                              <img src={imgUrl} alt={item.name} className="w-full h-full object-cover group-hover/card:scale-105 transition-transform duration-300" />

                              

                              {/* Hover Action Overlays */}

                              <div className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover/card:opacity-100 transition-opacity flex items-center justify-center gap-2">

                                <button

                                  type="button"

                                  onClick={() => {

                                    setRenamingAvatarName(item.name);

                                    setRenameAvatarInput(item.name);

                                  }}

                                  className="w-7 h-7 bg-white/95 hover:bg-white text-slate-700 hover:text-slate-900 rounded-full flex items-center justify-center shadow-xs transition-colors"

                                  title="重命名"

                                >

                                  <Edit className="w-3.5 h-3.5" />

                                </button>

                                <button

                                  type="button"

                                  onClick={() => handleDeleteFromAvatarLibrary(item.name)}

                                  className="w-7 h-7 bg-white/95 hover:bg-red-600 text-slate-700 hover:text-white rounded-full flex items-center justify-center shadow-xs transition-colors"

                                  title="删除"

                                >

                                  <Trash2 className="w-3.5 h-3.5" />

                                </button>

                              </div>

                            </div>



                            {/* Name & Size Info */}

                            <div className="p-2.5 flex flex-col gap-1">

                              {isRenaming ? (

                                <div className="flex gap-1 items-center">

                                  <input 

                                    type="text" 

                                    value={renameAvatarInput}

                                    onChange={(e) => setRenameAvatarInput(e.target.value)}

                                    onKeyDown={(e) => {

                                      if (e.key === 'Enter') {

                                        handleRenameInAvatarLibrary(item.name, renameAvatarInput);

                                        setRenamingAvatarName('');

                                      } else if (e.key === 'Escape') {

                                        setRenamingAvatarName('');

                                      }

                                    }}

                                    className="w-full border border-blue-400 rounded px-1.5 py-0.5 text-[11px] text-slate-800 focus:outline-none"

                                    autoFocus

                                  />

                                  <button

                                    type="button"

                                    onClick={() => {

                                      handleRenameInAvatarLibrary(item.name, renameAvatarInput);

                                      setRenamingAvatarName('');

                                    }}

                                    className="p-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100"

                                  >

                                    <Check className="w-3 h-3" />

                                  </button>

                                </div>

                              ) : (

                                <div className="flex justify-between items-center gap-1">

                                  <span className="text-[11px] font-semibold text-slate-700 truncate" title={item.name}>

                                    {item.name}

                                  </span>

                                </div>

                              )}

                              <div className="flex justify-between items-center text-[9px] text-slate-400 font-mono">

                                <span>{(item.size / 1024).toFixed(1)} KB</span>

                                <span>{new Date(item.mtime * 1000).toLocaleDateString()}</span>

                              </div>

                            </div>

                          </div>

                        );

                      })}

                    </div>

                  )}

                </div>



              </div>



              {/* Modal Footer */}

              <div className="p-5 border-t border-slate-100 flex justify-end bg-slate-50/35">

                <button 

                  type="button"

                  onClick={() => {

                    setShowLibraryManager(false);

                    setRenamingAvatarName('');

                  }}

                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg shadow-sm transition-all active:scale-[0.98]"

                >

                  关闭

                </button>

              </div>



            </div>

          </div>

        )}



      </main>



    </div>

  );

}

interface GroupSyncSummary {
  syncedCount: number;
  addedCount: number;
  skippedCount: number;
  updatedCount: number;
  disabledCount: number;
  invalidCount: number;
  totalGroups: number;
  enabledCount: number;
  disabledTotalCount: number;
  memberRanges: Record<string, number>;
  scoreRanges: Record<string, number>;
  hasScore: boolean;
  errors: string[];
  invalidGroups: Array<{ id: string; title: string; username?: string }>;
}

