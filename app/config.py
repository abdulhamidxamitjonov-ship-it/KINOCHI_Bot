from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    bot_token:str; bot_username:str=''; admin_id:int|None=None; admin_ids:str=''; database_url:str
    ad_channel_id:int|None=None; ad_channel_url:str=''; private_movie_channel_id:int|None=None; private_movie_channel_url:str=''
    uzcard_card_number:str=''; uzcard_card_name:str=''; humo_card_number:str=''; humo_card_name:str=''; visa_card_number:str=''; visa_card_name:str=''; master_card_number:str=''; master_card_name:str=''; log_level:str='INFO'
    model_config=SettingsConfigDict(env_file='.env',extra='ignore')
    @property
    def admins(self):
        ids=[]
        if self.admin_id: ids.append(self.admin_id)
        for x in self.admin_ids.split(','):
            if x.strip().isdigit(): ids.append(int(x.strip()))
        return set(ids)
settings=Settings()
