package org.kanglish.app

import android.app.Application
import android.content.Context
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.inference.TeacherService
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class PrivacyDefaultsTest {
    @Test fun freshInstallHasNoBundledCredentialsOrCloudOptIn() {
        val teacher = TeacherService(RuntimeEnvironment.getApplication())
        assertFalse(teacher.isTeacherEnabled)
        assertEquals("", teacher.geminiKey)
        assertEquals("", teacher.groqKey)
    }

    @Test fun oldEnabledSettingDoesNotImplyConsentToNewCloudMode() {
        val app = RuntimeEnvironment.getApplication()
        app.getSharedPreferences("teacher_prefs", Context.MODE_PRIVATE).edit()
            .putBoolean("pref_teacher_enabled", true).commit()
        val teacher = TeacherService(app)
        assertFalse(teacher.isTeacherEnabled)
        teacher.isTeacherEnabled = true
        assertTrue(TeacherService(app).isTeacherEnabled)
    }
}
