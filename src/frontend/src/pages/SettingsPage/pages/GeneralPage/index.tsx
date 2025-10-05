import { cloneDeep } from "lodash";
import { useContext, useState } from "react";
import { useParams } from "react-router-dom";
import { Input } from "@/components/ui/input";
import {
  EDIT_PASSWORD_ALERT_LIST,
  EDIT_PASSWORD_ERROR_ALERT,
  SAVE_ERROR_ALERT,
  SAVE_SUCCESS_ALERT,
} from "@/constants/alerts_constants";
import { usePostAddApiKey } from "@/controllers/API/queries/api-keys";
import {
  useResetPassword,
  useUpdateUser,
} from "@/controllers/API/queries/auth";
import { useGetProfilePicturesQuery } from "@/controllers/API/queries/files";
import { useGetPreflightQuery } from "@/controllers/API/queries/preflight/use-get-preflight";
import { CustomTermsLinks } from "@/customization/components/custom-terms-links";
import { ENABLE_PROFILE_ICONS } from "@/customization/feature-flags";
import useAuthStore from "@/stores/authStore";
import { useDevSettingsStore } from "@/stores/devSettingsStore";
import { CONTROL_PATCH_USER_STATE } from "../../../../constants/constants";
import { AuthContext } from "../../../../contexts/authContext";
import useAlertStore from "../../../../stores/alertStore";
import { useStoreStore } from "../../../../stores/storeStore";
import type {
  inputHandlerEventType,
  patchUserInputStateType,
} from "../../../../types/components";
import useScrollToElement from "../hooks/use-scroll-to-element";
import GeneralPageHeaderComponent from "./components/GeneralPageHeader";
import PasswordFormComponent from "./components/PasswordForm";
import ProfilePictureFormComponent from "./components/ProfilePictureForm";

function WorkspaceDevServerSettings() {
  const defaultDevUrl = useDevSettingsStore((s) => s.defaultDevUrl);
  const setDefaultDevUrl = useDevSettingsStore((s) => s.setDefaultDevUrl);
  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm">Default Dev URL</label>
      <div className="flex items-center gap-2">
        <Input
          value={defaultDevUrl}
          onChange={(e) => setDefaultDevUrl(e.target.value)}
          placeholder="http://localhost:5173/"
        />
      </div>
      <div className="text-xs text-muted-foreground">
        Used by the UI Builder for Build & Preview and as a fallback preview
        URL.
      </div>
    </div>
  );
}

export const GeneralPage = () => {
  const { scrollId } = useParams();

  const [inputState, setInputState] = useState<patchUserInputStateType>(
    CONTROL_PATCH_USER_STATE,
  );

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { userData, setUserData } = useContext(AuthContext);
  const { password, cnfPassword, profilePicture } = inputState;
  const autoLogin = useAuthStore((state) => state.autoLogin);

  const { storeApiKey } = useContext(AuthContext);
  const setHasApiKey = useStoreStore((state) => state.updateHasApiKey);
  const setValidApiKey = useStoreStore((state) => state.updateValidApiKey);
  const setLoadingApiKey = useStoreStore((state) => state.updateLoadingApiKey);

  const { mutate: mutateResetPassword } = useResetPassword();
  const { mutate: mutatePatchUser } = useUpdateUser();

  const handlePatchPassword = () => {
    if (password !== cnfPassword) {
      setErrorData({
        title: EDIT_PASSWORD_ERROR_ALERT,
        list: [EDIT_PASSWORD_ALERT_LIST],
      });
      return;
    }

    if (password !== "") {
      mutateResetPassword(
        { user_id: userData!.id, password: { password } },
        {
          onSuccess: () => {
            handleInput({ target: { name: "password", value: "" } });
            handleInput({ target: { name: "cnfPassword", value: "" } });
            setSuccessData({ title: SAVE_SUCCESS_ALERT });
          },
          onError: (error) => {
            setErrorData({
              title: SAVE_ERROR_ALERT,
              list: [(error as any)?.response?.data?.detail],
            });
          },
        },
      );
    }
  };

  const handleGetProfilePictures = useGetProfilePicturesQuery();

  const handlePatchProfilePicture = (profile_picture) => {
    if (profile_picture !== "") {
      mutatePatchUser(
        { user_id: userData!.id, user: { profile_image: profile_picture } },
        {
          onSuccess: () => {
            const newUserData = cloneDeep(userData);
            newUserData!.profile_image = profile_picture;
            setUserData(newUserData);
            setSuccessData({ title: SAVE_SUCCESS_ALERT });
          },
          onError: (error) => {
            setErrorData({
              title: SAVE_ERROR_ALERT,
              list: [(error as any)?.response?.data?.detail],
            });
          },
        },
      );
    }
  };

  useScrollToElement(scrollId);

  const { mutate } = usePostAddApiKey({
    onSuccess: () => {
      setSuccessData({ title: "API key saved successfully" });
      setHasApiKey(true);
      setValidApiKey(true);
      setLoadingApiKey(false);
      handleInput({ target: { name: "apikey", value: "" } });
    },
    onError: (error) => {
      setErrorData({
        title: "API key save error",
        list: [(error as any)?.response?.data?.detail],
      });
      setHasApiKey(false);
      setValidApiKey(false);
      setLoadingApiKey(false);
    },
  });

  const _handleSaveKey = (apikey: string) => {
    if (apikey) {
      mutate({ key: apikey });
      storeApiKey(apikey);
    }
  };

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  const {
    data: preflight,
    isLoading: preflightLoading,
    error: preflightError,
    refetch: refetchPreflight,
  } = useGetPreflightQuery(undefined, { enabled: true });

  const badge = (label: string, ok: boolean) => (
    <span
      className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ${
        ok ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
      }`}
    >
      {label}
    </span>
  );

  return (
    <div className="flex h-full w-full flex-col gap-6 overflow-x-hidden">
      <GeneralPageHeaderComponent />

      <div className="flex w-full flex-col gap-6">
        {ENABLE_PROFILE_ICONS && (
          <ProfilePictureFormComponent
            profilePicture={profilePicture}
            handleInput={handleInput}
            handlePatchProfilePicture={handlePatchProfilePicture}
            handleGetProfilePictures={handleGetProfilePictures}
            userData={userData}
          />
        )}

        {!autoLogin && (
          <PasswordFormComponent
            password={password}
            cnfPassword={cnfPassword}
            handleInput={handleInput}
            handlePatchPassword={handlePatchPassword}
          />
        )}

        <div className="rounded-md border border-muted-200 p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold">Environment Preflight</h3>
            <button
              className="rounded border px-2 py-1 text-xs"
              onClick={() => refetchPreflight()}
              disabled={preflightLoading}
            >
              {preflightLoading ? "Checking..." : "Recheck"}
            </button>
          </div>

          {preflightError && (
            <div className="text-sm text-red-600">
              Failed to run preflight checks.
            </div>
          )}

          {!preflightError && (
            <div className="flex flex-col gap-3">
              <div className="text-sm">
                Overall:{" "}
                {badge(
                  preflight?.ok ? "All good" : "Attention needed",
                  Boolean(preflight?.ok),
                )}
              </div>

              <div className="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-3">
                {preflight?.checks?.map((c) => (
                  <div
                    key={c.name}
                    className="rounded-md border border-muted-200 p-3"
                  >
                    <div className="mb-1 flex items-center justify-between">
                      <div className="text-sm font-medium">{c.name}</div>
                      <div className="flex gap-2">
                        {badge("installed", c.installed)}
                        {c.meets_minimum == null
                          ? null
                          : badge("min", c.meets_minimum)}
                      </div>
                    </div>
                    <div className="text-xs text-muted-700">
                      {c.version ? `version: ${c.version}` : "version: n/a"}
                    </div>
                    {c.note && (
                      <div className="mt-1 text-xs text-muted-700">
                        {c.note}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {preflight?.warnings?.length ? (
                <div className="rounded-md bg-yellow-50 p-3 text-xs text-yellow-900">
                  <div className="mb-1 font-semibold">Warnings</div>
                  <ul className="list-disc space-y-1 pl-4">
                    {preflight.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* Workspace Dev Server Defaults */}
        <div className="rounded-md border border-muted-200 p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold">Workspace Dev Server</h3>
          </div>
          <WorkspaceDevServerSettings />
        </div>
      </div>

      <CustomTermsLinks />
    </div>
  );
};

export default GeneralPage;
