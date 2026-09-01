/**
 * API 호출을 담당하는 모듈입니다.
 * 각 함수는 백엔드 API 명세의 요구사항 ID를 주석으로 포함합니다.
 *
 * 템플릿 기본 예시와 우리 팀의 실제 구현(app/apis/*)이 경로/요청/응답 형태에서
 * 차이가 있어, 이 모듈에서 프론트엔드가 기대하는 형태로 변환(adapter)합니다.
 *  - 인증: /auth/* (login 은 JSON body)
 *  - 목록 응답: {items, page, size, total, total_pages} → 배열로 평탄화
 *  - 식별자: 백엔드 uuid → 프론트 id
 *  - 유저 enum: role PENDING/STAFF/ADMIN ↔ pending/staff/admin, gender M/F ↔ male/female
 *  - 진료기록/AI 예측: 환자 하위 리소스 경로(/patients/{id}/...)
 */

const API_BASE = '/api/v1';

const DEPT_TO_SERVER = {
    developer: 'DEV',
    'medical team': 'MEDICAL',
    researcher: 'RESEARCH',
    '개발팀': 'DEV',
    '의료진': 'MEDICAL',
    '연구진': 'RESEARCH',
    DEV: 'DEV',
    MEDICAL: 'MEDICAL',
    RESEARCH: 'RESEARCH',
};

const apis = {
    isRefreshing: false,
    refreshSubscribers: [],

    // --- 변환 헬퍼 ---
    _toClientRole(role) {
        return String(role || '').toLowerCase();
    },
    _toServerRole(role) {
        return String(role || '').toUpperCase();
    },
    _toClientGender(gender) {
        if (gender === 'M') return 'male';
        if (gender === 'F') return 'female';
        return gender;
    },
    _toServerGender(gender) {
        if (gender === 'male') return 'M';
        if (gender === 'female') return 'F';
        return gender;
    },
    _toServerDept(dept) {
        if (!dept) return dept;
        return DEPT_TO_SERVER[dept] || String(dept).toUpperCase();
    },
    _adaptUser(u) {
        if (!u) return u;
        return {
            ...u,
            id: u.uuid ?? u.id,
            role: this._toClientRole(u.role),
            gender: this._toClientGender(u.gender),
            phone_number: u.phone_number ?? u.phone,
        };
    },
    _adaptPatient(p) {
        if (!p) return p;
        return {
            ...p,
            id: p.uuid ?? p.id,
            phone_number: p.phone ?? p.phone_number,
        };
    },
    _adaptRecordListItem(r) {
        if (!r) return r;
        return { ...r, id: r.uuid ?? r.id };
    },
    _unwrapList(data) {
        if (Array.isArray(data)) return data;
        if (data && Array.isArray(data.items)) return data.items;
        return [];
    },

    subscribeTokenRefresh(cb) {
        this.refreshSubscribers.push(cb);
    },

    onTokenRefreshed(token) {
        this.refreshSubscribers.map(cb => cb(token));
        this.refreshSubscribers = [];
    },

    async request(url, options = {}, skipAlert = false) {
        const headers = { ...options.headers };
        if (state.token) {
            headers['Authorization'] = `Bearer ${state.token}`;
        }

        try {
            const response = await fetch(`${API_BASE}${url}`, { ...options, headers });

            // 401 Unauthorized 처리 (토큰 만료 시 리프레시 시도)
            if (response.status === 401) {
                // 로그인 요청에서 401은 리프레시 대상이 아님
                if (url === '/auth/login') {
                    return { status: 401 };
                }

                // 토큰이 없는 경우 리프레시 시도 없이 로그아웃
                if (!state.token) {
                    await logout();
                    return null;
                }

                // 이미 리프레시 중이면 대기열에 추가
                if (this.isRefreshing) {
                    return new Promise((resolve) => {
                        this.subscribeTokenRefresh(token => {
                            headers['Authorization'] = `Bearer ${token}`;
                            resolve(this.request(url, options, skipAlert));
                        });
                    });
                }

                this.isRefreshing = true;
                try {
                    const refreshResponse = await fetch(`${API_BASE}/auth/refresh`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });

                    if (refreshResponse.ok) {
                        const data = await refreshResponse.json();
                        state.token = data.access_token;
                        localStorage.setItem('token', state.token);

                        this.isRefreshing = false;
                        this.onTokenRefreshed(state.token);

                        // 원래 요청 재시도
                        headers['Authorization'] = `Bearer ${state.token}`;
                        return await this.request(url, options, skipAlert);
                    } else {
                        // 리프레시 실패 시 로그아웃
                        this.isRefreshing = false;
                        await logout();
                        return null;
                    }
                } catch (refreshErr) {
                    this.isRefreshing = false;
                    await logout();
                    return null;
                }
            }

            if (!response.ok) {
                let error;
                try {
                    error = await response.json();
                } catch (e) {
                    error = { detail: '서버 응답 처리 중 오류가 발생했습니다.' };
                }

                let msg = error.detail || '요청 중 오류가 발생했습니다.';
                if (Array.isArray(msg)) {
                    msg = msg.map(e => {
                        let text = e.msg;
                        text = text.replace(/^Value error, /, '');
                        text = text.replace(/^Field required, /, '');
                        if (text === 'Field required') text = '필수 입력 항목입니다.';
                        return text;
                    }).join(', ');
                }

                // 특정 메시지 처리
                const passwordErrorMessage = "비밀번호는 대소문자, 특수문자, 숫자를 각 1개씩 포함한 8자리 이상이어야 합니다.";
                if (msg.includes(passwordErrorMessage)) {
                    msg = passwordErrorMessage;
                } else if (response.status >= 500) {
                    msg = "잠시후 다시 시도해주세요.";
                }

                const errObj = new Error(msg);
                errObj.status = response.status;
                throw errObj;
            }
            if (response.status === 204) return null;
            return await response.json();
        } catch (err) {
            if (url !== '/auth/login' && !skipAlert) {
                utils.showAlert(err.message, 'error', '오류');
            }
            throw err;
        }
    },

    // --- Auth & Users ---
    /**
     * 회원가입
     * [REQ-USER-001] 사내 구성원은 이메일, 비밀번호, 이름, 소속 부서, 성별, 전화번호를 입력하여 회원가입을 할 수 있다.
     */
    async signup(userData) {
        const payload = {
            email: userData.email,
            password: userData.password,
            name: userData.name,
            phone_number: userData.phone_number,
            department: this._toServerDept(userData.department),
            gender: this._toServerGender(userData.gender),
        };
        const created = await this.request('/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }, true);
        return this._adaptUser(created);
    },

    /**
     * 로그인
     * [REQ-USER-002] 가입된 이메일과 비밀번호로 로그인을 할 수 있다.
     */
    async login(email, password) {
        return await this.request('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        }, true);
    },

    /**
     * 토큰 갱신
     * [NFR-USER-001] 로그인 성공 시 Access Token(JSON Body)과 Refresh Token(HTTP-only Cookie)이 발급된다.
     */
    async refresh() {
        return await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
    },

    /**
     * 로그아웃
     * [REQ-USER-003] 로그인된 사용자는 로그아웃을 할 수 있다.
     */
    async logout() {
        return await this.request('/auth/logout', { method: 'POST' });
    },

    /**
     * 내 정보 조회
     * [REQ-USER-006] 로그인된 사용자는 본인의 정보를 조회할 수 있다.
     */
    async getMe() {
        return this._adaptUser(await this.request('/users/me'));
    },

    /**
     * 내 정보 수정
     * [REQ-USER-007] 로그인된 사용자는 본인의 정보(부서, 전화번호)를 수정할 수 있다.
     */
    async updateMe(userData) {
        const payload = {};
        if (userData.department !== undefined) payload.department = this._toServerDept(userData.department);
        if (userData.phone_number !== undefined) payload.phone_number = userData.phone_number;
        return this._adaptUser(await this.request('/users/me', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }, true));
    },

    /**
     * 비밀번호 변경
     * [REQ-USER-008] 로그인된 사용자는 본인의 비밀번호를 변경할 수 있다.
     */
    async updatePassword(passwordData) {
        return await this.request('/users/me/password', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(passwordData)
        }, true);
    },

    /**
     * 회원 탈퇴
     * [REQ-USER-009] 로그인된 사용자는 회원 탈퇴를 할 수 있다.
     */
    async deleteMe() {
        return await this.request('/users/me', { method: 'DELETE' });
    },

    // --- Patients ---

    /**
     * 환자 등록
     * [REQ-PTNT-001] 사내 의료인 역할을 가진 유저만 환자를 신규 등록할 수 있다.
     */
    async createPatient(patientData) {
        const payload = {
            name: patientData.name,
            age: patientData.age,
            gender: patientData.gender,
            phone: patientData.phone_number ?? patientData.phone,
        };
        return this._adaptPatient(await this.request('/patients', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }));
    },

    /**
     * 환자 목록 조회
     * [REQ-PTNT-002] 로그인된 사내 개발진, 의료 실무진, 연구진은 환자 목록을 조회할 수 있다.
     */
    async getPatients(params = {}) {
        const query = new URLSearchParams();
        if (params.name) query.set('search', params.name);
        if (params.search) query.set('search', params.search);
        if (params.gender) query.set('gender', params.gender);
        if (params.min_age) query.set('min_age', params.min_age);
        if (params.max_age) query.set('max_age', params.max_age);
        query.set('page', params.page || 1);
        query.set('size', params.size || 100);
        const data = await this.request(`/patients?${query.toString()}`);
        return this._unwrapList(data).map(p => this._adaptPatient(p));
    },

    /**
     * 환자 상세 조회
     * [REQ-PTNT-003] 특정 환자의 상세 정보를 조회할 수 있다.
     */
    async getPatient(patientId) {
        return this._adaptPatient(await this.request(`/patients/${patientId}`));
    },

    /**
     * 환자 정보 수정
     * [REQ-PTNT-004] 특정 환자의 정보를 수정할 수 있다.
     */
    async updatePatient(patientId, patientData) {
        const payload = {};
        if (patientData.name !== undefined) payload.name = patientData.name;
        const phone = patientData.phone_number ?? patientData.phone;
        if (phone !== undefined) payload.phone = phone;
        return this._adaptPatient(await this.request(`/patients/${patientId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }));
    },

    /**
     * 환자 삭제
     * [REQ-PTNT-005] 특정 환자 정보를 삭제할 수 있다.
     */
    async deletePatient(patientId) {
        return await this.request(`/patients/${patientId}`, { method: 'DELETE' });
    },

    // --- Medical Records ---

    /**
     * 진료 기록 등록
     * [REQ-MDR-001] 사내 의료인 역할을 가진 유저만 환자의 진료 기록을 등록할 수 있다.
     */
    async createMedicalRecord(formData) {
        const patientId = formData.get('patient_id');
        return await this.request(`/patients/${patientId}/medical-records`, {
            method: 'POST',
            body: formData
        });
    },

    /**
     * 환자별 진료 기록 목록 조회
     * [REQ-MDR-002] 특정 환자의 진료 기록 목록을 조회할 수 있다.
     */
    async getPatientMedicalRecords(patientId) {
        const data = await this.request(`/patients/${patientId}/medical-records?page=1&size=100`);
        return this._unwrapList(data).map(r => this._adaptRecordListItem(r));
    },

    /**
     * 진료 기록 상세 조회
     * [REQ-MDR-003] 특정 진료 기록의 상세 내용을 조회할 수 있다.
     */
    async getMedicalRecord(patientId, recordId) {
        const d = await this.request(`/patients/${patientId}/medical-records/${recordId}`);
        if (!d) return d;
        const firstImage = Array.isArray(d.xray_images) ? d.xray_images[0]
            : d.xray_image ? d.xray_image : null;
        return {
            ...d,
            id: d.uuid ?? d.id,
            patient_id: d.patient_id ?? patientId,
            xray_image_url: (firstImage && (firstImage.url || firstImage.image_url)) || d.xray_image_url || '',
        };
    },

    // --- AI Prediction ---

    /**
     * AI 폐렴 예측 수행
     * [REQ-PRED-001] 진료기록에 등록된 X-ray 이미지를 활용하여 폐렴 여부를 예측한다.
     */
    async predictPneumonia(patientId, recordId) {
        return await this.request(
            `/patients/${patientId}/medical-records/${recordId}/ai-prediction`,
            { method: 'POST' }
        );
    },

    /**
     * AI 예측 결과 목록 조회
     * [REQ-PRED-002] 특정 진료기록에 대해 수행된 모든 AI 예측 결과 목록을 조회한다.
     * 백엔드는 환자 단위(/patients/{id}/ai-predictions)로 제공하므로 진료기록 기준으로 필터링한다.
     */
    async getMedicalRecordAnalyses(patientId, recordId) {
        const data = await this.request(`/patients/${patientId}/ai-predictions?page=1&size=100`);
        return this._unwrapList(data)
            .filter(a => !recordId || a.medical_record_id === recordId)
            .map(a => ({
                ...a,
                is_pneumonia: a.is_pneumonia,
                confidence: a.confidence,
                ai_model: a.ai_model,
                created_at: a.predicted_at ?? a.created_at,
                heatmap_image_url: a.heatmap_image_url ?? null,
            }));
    },

    // --- Admin ---

    /**
     * 전체 유저 목록 조회 (관리자 전용)
     * [REQ-USER-004] 관리자 권한을 가진 유저는 전체 유저 목록을 조회할 수 있다.
     */
    async adminGetUsers(params = {}) {
        const query = new URLSearchParams();
        if (params.query) query.set('search', params.query);
        if (params.search) query.set('search', params.search);
        if (params.department) query.set('department', this._toServerDept(params.department));
        query.set('page', params.page || 1);
        query.set('size', params.size || 100);
        const data = await this.request(`/admin/users?${query.toString()}`);
        return this._unwrapList(data).map(u => this._adaptUser(u));
    },

    /**
     * 유저 권한 수정 (관리자 전용)
     * [REQ-USER-005] 관리자 권한을 가진 유저는 다른 유저의 권한을 수정할 수 있다.
     */
    async adminUpdateUserRole(roleData) {
        const userId = roleData.user_id ?? roleData.userId;
        const updated = await this.request(`/admin/users/${userId}/role`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: this._toServerRole(roleData.new_role ?? roleData.role) })
        });
        return this._adaptUser(updated);
    }
};
